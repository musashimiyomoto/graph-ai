"""Public workflow webhook API tests."""

from http import HTTPStatus

import pytest

from enums import ExecutionSource, InputNodeFormat, NodeType
from tests.factories import EdgeFactory, NodeFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase
from utils.webhooks import build_webhook_path


class TestWebhookTrigger(BaseTestCase):
    """Tests for ``POST /webhooks/{token}``."""

    async def _create_workflow(self, user_id: int, *, enabled: bool = True) -> int:
        """Create a minimal webhook-input workflow and return its ID."""
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user_id
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={
                "label": "Webhook Input",
                "format": (
                    InputNodeFormat.WEBHOOK.value
                    if enabled
                    else InputNodeFormat.TXT.value
                ),
            },
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=output_node.id,
        )
        return workflow.id

    @pytest.mark.asyncio
    async def test_json_body_queues_webhook_execution(self) -> None:
        """A signed public request becomes a webhook-sourced execution."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"])

        response = await self.client.post(
            url=build_webhook_path(workflow_id),
            json={"event": "lead.created", "score": 7},
            headers={"Idempotency-Key": "lead-42"},
        )

        data = await self.assert_response_dict(response=response)
        if data["workflow_id"] != workflow_id:
            pytest.fail("Webhook execution targeted the wrong workflow")
        if data["source"] != ExecutionSource.WEBHOOK.value:
            pytest.fail("Execution was not tagged with the webhook source")
        expected = '{"event":"lead.created","score":7}'
        if data["input_data"] != {"value": expected}:
            pytest.fail("Webhook JSON was not normalized into workflow input")
        event = data["trigger_event"]
        if event["external_event_id"] != "lead-42":
            pytest.fail("Webhook event ID was not persisted")
        if event["raw_retention"] != "discard":
            pytest.fail("Webhook raw payload retention must be explicit")

    @pytest.mark.asyncio
    async def test_plain_text_body_is_preserved(self) -> None:
        """Non-JSON webhook bodies pass through as UTF-8 text."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"])

        response = await self.client.post(
            url=build_webhook_path(workflow_id),
            content="hello from webhook",
            headers={
                "Content-Type": "text/plain",
                "Idempotency-Key": "plain-1",
            },
        )

        data = await self.assert_response_dict(response=response)
        if data["input_data"] != {"value": "hello from webhook"}:
            pytest.fail("Plain webhook text was changed")

    @pytest.mark.asyncio
    async def test_invalid_signature_is_not_found(self) -> None:
        """A tampered token does not reveal whether its workflow exists."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"])
        token = build_webhook_path(workflow_id).rsplit("/", maxsplit=1)[-1]

        response = await self.client.post(
            url=f"/webhooks/{token}tampered", content="ignored"
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail(f"Expected 404, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_disabled_webhook_input_is_not_found(self) -> None:
        """The signed URL stops working when Input is changed to another format."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"], enabled=False)

        response = await self.client.post(
            url=build_webhook_path(workflow_id), content="ignored"
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail(f"Expected 404, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_invalid_json_is_rejected(self) -> None:
        """Malformed JSON receives a clear client error instead of a server error."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"])

        response = await self.client.post(
            url=build_webhook_path(workflow_id),
            content="{not-json",
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": "invalid-json-1",
            },
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail(f"Expected 400, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_repeated_event_id_returns_the_original_execution(self) -> None:
        """Provider retries are idempotent even when the HTTP request repeats."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"])
        headers = {"Idempotency-Key": "provider-event-7"}

        first = await self.client.post(
            url=build_webhook_path(workflow_id), content="payload", headers=headers
        )
        second = await self.client.post(
            url=build_webhook_path(workflow_id), content="payload", headers=headers
        )

        first_data = await self.assert_response_dict(response=first)
        second_data = await self.assert_response_dict(response=second)
        if first_data["id"] != second_data["id"]:
            pytest.fail("A repeated external event created a duplicate execution")

    @pytest.mark.asyncio
    async def test_missing_idempotency_key_is_rejected(self) -> None:
        """Public webhook callers must provide a stable provider event ID."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"])

        response = await self.client.post(
            url=build_webhook_path(workflow_id), content="payload"
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail(f"Expected 400, got {response.status_code}")
