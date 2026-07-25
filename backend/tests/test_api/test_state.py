"""Typed durable state API tests."""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest

from db.models import Conversation, Execution
from enums import ExecutionSource, StateScope
from tests.factories import (
    ConversationFactory,
    ExecutionFactory,
    StateEntryFactory,
    WorkflowFactory,
)
from tests.test_api.base import BaseTestCase

_UPDATED_VERSION = 2


def _trigger_event(*, conversation_id: str, sender_id: str) -> dict:
    """Build a normalized web-chat trigger for state-scope tests."""
    return {
        "schema_version": 1,
        "channel": ExecutionSource.WEB_CHAT.value,
        "external_event_id": f"event-{conversation_id}",
        "sender": {"id": sender_id, "display_name": None, "address": None},
        "conversation": {"id": conversation_id, "thread_id": None},
        "locale": None,
        "message": {
            "kind": "text",
            "value": "hello",
            "artifact": None,
            "metadata": {},
        },
        "attachments": [],
        "occurred_at": datetime.now(tz=UTC).isoformat(),
        "metadata": {},
        "raw_retention": "discard",
    }


class TestStateAPI(BaseTestCase):
    """Tests for execution-authorized typed state scopes."""

    async def _create_context(
        self,
        *,
        user_id: int,
        workflow_id: int,
        sender_id: str = "visitor-a",
    ) -> tuple[Conversation, Execution]:
        """Create a conversation and execution that expose every state scope."""
        conversation = await ConversationFactory.create_async(
            session=self.session,
            owner_id=user_id,
            workflow_id=workflow_id,
            actor_id=sender_id,
        )
        execution = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow_id,
            source=ExecutionSource.WEB_CHAT,
            conversation_id=conversation.id,
            trigger_event=_trigger_event(
                conversation_id=conversation.external_conversation_id,
                sender_id=sender_id,
            ),
        )
        return conversation, execution

    @pytest.mark.asyncio
    async def test_state_lifecycle_keeps_typed_history_and_cas_versions(self) -> None:
        """Create/update/delete uses NodeValue, TTL metadata, CAS, and history."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        _, execution = await self._create_context(
            user_id=user["id"], workflow_id=workflow.id
        )
        url = f"/executions/{execution.id}/state/workflow/profile"

        created = await self.client.put(
            url=url,
            headers=headers,
            json={
                "value": {"kind": "json", "value": {"name": "Ada"}},
                "expected_version": 0,
                "ttl_seconds": 3600,
            },
        )
        created_data = await self.assert_response_dict(response=created)
        if created_data["version"] != 1 or created_data["value"]["kind"] != "json":
            pytest.fail("Typed state was not created at version 1")
        if created_data["expires_at"] is None:
            pytest.fail("State TTL was not persisted")

        updated = await self.client.put(
            url=url,
            headers=headers,
            json={
                "value": {"kind": "list", "value": ["Ada", "Grace"]},
                "expected_version": 1,
            },
        )
        updated_data = await self.assert_response_dict(response=updated)
        if (
            updated_data["version"] != _UPDATED_VERSION
            or updated_data["value"]["kind"] != "list"
        ):
            pytest.fail("Typed state was not updated to version 2")

        stale = await self.client.put(
            url=url,
            headers=headers,
            json={
                "value": {"kind": "text", "value": "stale"},
                "expected_version": 1,
            },
        )
        if stale.status_code != HTTPStatus.CONFLICT:
            pytest.fail(f"Expected stale CAS to return 409, got {stale.status_code}")

        deleted = await self.client.request(
            method="DELETE",
            url=url,
            headers=headers,
            json={"expected_version": 2},
        )
        if deleted.status_code != HTTPStatus.NO_CONTENT:
            pytest.fail(f"Expected 204, got {deleted.status_code}")

        missing = await self.client.get(url=url, headers=headers)
        if missing.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Deleted state remained readable")
        history = await self.client.get(url=f"{url}/history", headers=headers)
        rows = await self.assert_response_list(response=history)
        if [row["operation"] for row in rows] != ["delete", "update", "create"]:
            pytest.fail("State mutation history was not retained newest-first")

    @pytest.mark.asyncio
    async def test_scopes_share_only_across_their_declared_identity(self) -> None:
        """Execution, conversation, user, and workflow scopes have distinct reach."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        first_conversation, first = await self._create_context(
            user_id=user["id"], workflow_id=workflow.id
        )
        second_same_conversation = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source=ExecutionSource.WEB_CHAT,
            conversation_id=first_conversation.id,
            trigger_event=_trigger_event(
                conversation_id=first_conversation.external_conversation_id,
                sender_id="visitor-a",
            ),
        )
        _, different_conversation = await self._create_context(
            user_id=user["id"],
            workflow_id=workflow.id,
            sender_id="visitor-a",
        )

        cases = [
            (StateScope.EXECUTION, second_same_conversation.id, HTTPStatus.NOT_FOUND),
            (StateScope.CONVERSATION, second_same_conversation.id, HTTPStatus.OK),
            (StateScope.CONVERSATION, different_conversation.id, HTTPStatus.NOT_FOUND),
            (StateScope.USER, different_conversation.id, HTTPStatus.OK),
            (StateScope.WORKFLOW, different_conversation.id, HTTPStatus.OK),
        ]
        for scope in StateScope:
            response = await self.client.put(
                url=f"/executions/{first.id}/state/{scope.value}/shared-{scope.value}",
                headers=headers,
                json={"value": {"kind": "text", "value": scope.value}},
            )
            await self.assert_response_dict(response=response)

        for scope, execution_id, expected_status in cases:
            response = await self.client.get(
                url=(
                    f"/executions/{execution_id}/state/{scope.value}/"
                    f"shared-{scope.value}"
                ),
                headers=headers,
            )
            if response.status_code != expected_status:
                pytest.fail(
                    f"{scope.value} scope returned {response.status_code}, "
                    f"expected {expected_status}"
                )

    @pytest.mark.asyncio
    async def test_expired_state_is_not_readable(self) -> None:
        """TTL-expired rows behave as absent without losing future auditability."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        _, execution = await self._create_context(
            user_id=user["id"], workflow_id=workflow.id
        )
        await StateEntryFactory.create_async(
            session=self.session,
            owner_id=user["id"],
            workflow_id=workflow.id,
            scope=StateScope.WORKFLOW,
            scope_ref=str(workflow.id),
            key="expired",
            expires_at=datetime.now(tz=UTC) - timedelta(seconds=1),
        )

        response = await self.client.get(
            url=f"/executions/{execution.id}/state/workflow/expired",
            headers=headers,
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail(f"Expected 404, got {response.status_code}")
