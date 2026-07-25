"""Public embedded web-chat API tests."""

from http import HTTPStatus

import pytest

from enums import (
    ExecutionSource,
    ExecutionStatus,
    InputNodeFormat,
    NodeType,
    OutputNodeFormat,
)
from tests.factories import (
    ConversationFactory,
    EdgeFactory,
    ExecutionFactory,
    NodeFactory,
    WorkflowFactory,
)
from tests.test_api.base import BaseTestCase
from utils.web_chat import build_web_chat_path

_MIN_SESSION_ID_LENGTH = 16


class TestWebChatAPI(BaseTestCase):
    """Tests for the signed public web-chat surface."""

    async def _create_workflow(
        self,
        user_id: int,
        *,
        input_format: InputNodeFormat = InputNodeFormat.WEB_CHAT,
        output_format: OutputNodeFormat = OutputNodeFormat.WEB_CHAT,
    ) -> int:
        """Create a minimal channel-configured workflow and return its ID."""
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user_id
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Visitor", "format": input_format.value},
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Reply", "format": output_format.value},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=output_node.id,
        )
        return workflow.id

    @pytest.mark.asyncio
    async def test_public_message_queues_web_chat_execution(self) -> None:
        """A visitor message queues a web-chat sourced run without auth."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"])

        response = await self.client.post(
            url=f"{build_web_chat_path(workflow_id)}/executions",
            json={
                "value": "Hello",
                "event_id": "message-1",
                "locale": "en-US",
            },
        )

        data = await self.assert_response_dict(response=response)
        if data["workflow_id"] != workflow_id:
            pytest.fail("Web chat targeted the wrong workflow")
        if data["source"] != ExecutionSource.WEB_CHAT.value:
            pytest.fail("Execution was not tagged with the web_chat source")
        if data["input_data"] != {"value": "Hello"}:
            pytest.fail("Visitor message was not persisted as execution input")
        if len(data["session_id"]) < _MIN_SESSION_ID_LENGTH:
            pytest.fail("Web chat did not issue an opaque durable session ID")
        if not data["trigger_event"]["conversation"]["id"]:
            pytest.fail("Web-chat conversation identity was not persisted")

    @pytest.mark.asyncio
    async def test_both_channel_formats_must_be_enabled(self) -> None:
        """A signed URL stays disabled until Input and Output both use web_chat."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(
            user["id"], output_format=OutputNodeFormat.TXT
        )

        response = await self.client.post(
            url=f"{build_web_chat_path(workflow_id)}/executions",
            json={
                "value": "Hello",
                "event_id": "message-disabled",
                "conversation_id": "visitor-1",
            },
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail(f"Expected 404, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_repeated_message_event_is_idempotent(self) -> None:
        """A retried visitor request returns the original queued execution."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"])
        payload = {
            "value": "Hello",
            "event_id": "message-retry-1",
            "conversation_id": "visitor-1",
        }
        url = f"{build_web_chat_path(workflow_id)}/executions"

        first = await self.client.post(url=url, json=payload)
        second = await self.client.post(url=url, json=payload)

        first_data = await self.assert_response_dict(response=first)
        second_data = await self.assert_response_dict(response=second)
        if first_data["id"] != second_data["id"]:
            pytest.fail("A web-chat retry created a duplicate execution")

    @pytest.mark.asyncio
    async def test_issued_session_reuses_the_durable_conversation(self) -> None:
        """Later messages carrying the issued session stay in one conversation."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"])
        url = f"{build_web_chat_path(workflow_id)}/executions"

        first = await self.client.post(
            url=url,
            json={"value": "Hello", "event_id": "session-message-1"},
        )
        first_data = await self.assert_response_dict(response=first)
        second = await self.client.post(
            url=url,
            json={
                "value": "Again",
                "event_id": "session-message-2",
                "session_id": first_data["session_id"],
            },
        )
        second_data = await self.assert_response_dict(response=second)

        if second_data["session_id"] != first_data["session_id"]:
            pytest.fail("Web chat replaced the server-issued session")
        if (
            second_data["trigger_event"]["conversation"]
            != first_data["trigger_event"]["conversation"]
        ):
            pytest.fail("Messages from one session used different conversations")

    @pytest.mark.asyncio
    async def test_execution_cannot_be_read_through_another_workflow(self) -> None:
        """A valid token cannot expose an execution belonging to another workflow."""
        user, _ = await self.create_user_and_get_token()
        first_id = await self._create_workflow(user["id"])
        second_id = await self._create_workflow(user["id"])
        execution = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=second_id,
            source=ExecutionSource.WEB_CHAT,
        )

        response = await self.client.get(
            url=(
                f"{build_web_chat_path(first_id)}/executions/{execution.id}"
                "?session_id=missing-session-id"
            )
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail(f"Expected 404, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_terminal_execution_streams_public_status(self) -> None:
        """A completed web-chat run is available through the public SSE endpoint."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"])
        conversation = await ConversationFactory.create_async(
            session=self.session,
            owner_id=user["id"],
            workflow_id=workflow_id,
        )
        execution = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow_id,
            source=ExecutionSource.WEB_CHAT,
            conversation_id=conversation.id,
            status=ExecutionStatus.SUCCESS,
            output_data={"value": "Hi there"},
        )

        response = await self.client.get(
            url=(
                f"{build_web_chat_path(workflow_id)}/executions/"
                f"{execution.id}/stream?session_id={conversation.public_id}"
            )
        )

        if response.status_code != HTTPStatus.OK:
            pytest.fail(f"Expected 200, got {response.status_code}")
        if '"source": "web_chat"' not in response.text:
            pytest.fail("Public stream did not include the web-chat execution")

    @pytest.mark.asyncio
    async def test_public_execution_requires_its_own_session(self) -> None:
        """One visitor session cannot read another visitor's execution."""
        user, _ = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow(user["id"])
        first = await self.client.post(
            url=f"{build_web_chat_path(workflow_id)}/executions",
            json={"value": "First", "event_id": "session-first"},
        )
        second = await self.client.post(
            url=f"{build_web_chat_path(workflow_id)}/executions",
            json={"value": "Second", "event_id": "session-second"},
        )
        first_data = await self.assert_response_dict(response=first)
        second_data = await self.assert_response_dict(response=second)

        response = await self.client.get(
            url=(
                f"{build_web_chat_path(workflow_id)}/executions/{first_data['id']}"
                f"?session_id={second_data['session_id']}"
            )
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail(f"Expected 404, got {response.status_code}")
