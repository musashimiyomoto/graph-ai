"""Execution API tests."""

from http import HTTPStatus
from typing import Self

import httpx
import pytest

from enums import ExecutionStatus, NodeType
from tests.factories import EdgeFactory, ExecutionFactory, NodeFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase


class TestExecutionCreate(BaseTestCase):
    """Tests for POST /executions."""

    url = "/executions"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful run creation returns finalized execution."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
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

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(
            data,
            {"id", "workflow_id", "status", "started_at", "output_data", "error"},
        )
        if data["workflow_id"] != workflow.id:
            pytest.fail("Execution workflow_id did not match request")
        if data["status"] != ExecutionStatus.SUCCESS:
            pytest.fail("Execution status did not match success state")
        if data["output_data"] != {"value": "hello"}:
            pytest.fail("Execution output did not match expected value")
        if data["error"] is not None:
            pytest.fail("Execution error should be null for success")

    @pytest.mark.asyncio
    async def test_ok_with_web_search_node(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Execution succeeds with web search node in the path."""

        class DummyResponse:
            """Dummy HTTP response for web search tests."""

            status_code = HTTPStatus.OK
            text = ""

            def raise_for_status(self) -> None:
                """Keep successful status."""

            def json(self) -> dict:
                """Return mock DuckDuckGo payload."""
                return {
                    "AbstractText": "DuckDuckGo is a privacy-focused search engine.",
                    "AbstractURL": "https://duckduckgo.com/about",
                    "RelatedTopics": [
                        {
                            "Text": "DuckDuckGo Search",
                            "FirstURL": "https://duckduckgo.com",
                        }
                    ],
                }

        class DummyAsyncClient:
            """Dummy async client that returns fixed payload."""

            def __init__(self, *args: object, **kwargs: object) -> None:
                """Allow constructing with any httpx kwargs."""

            async def __aenter__(self) -> Self:
                """Enter async context manager."""
                return self

            async def __aexit__(
                self,
                exc_type: type[BaseException] | None,
                exc: BaseException | None,
                tb: object,
            ) -> bool:
                """Exit async context manager."""
                del exc_type, exc, tb
                return False

            async def get(self, *args: object, **kwargs: object) -> DummyResponse:
                """Return a successful response."""
                del args, kwargs
                return DummyResponse()

        monkeypatch.setattr("nodes.web_search.httpx.AsyncClient", DummyAsyncClient)

        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        web_search_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.WEB_SEARCH,
            data={"label": "Web Search", "max_results": 2},
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
            target_node_id=web_search_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=web_search_node.id,
            target_node_id=output_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "duckduckgo"}},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["status"] != ExecutionStatus.SUCCESS:
            pytest.fail("Execution with web search node should succeed")
        output_value = (
            data.get("output_data", {}).get("value")
            if isinstance(data.get("output_data"), dict)
            else None
        )
        if not isinstance(output_value, str) or "DuckDuckGo" not in output_value:
            pytest.fail("Execution output does not contain expected web search text")

    @pytest.mark.asyncio
    async def test_web_search_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Execution is marked as failed when web search request fails."""

        class FailingAsyncClient:
            """Dummy async client that raises a timeout."""

            def __init__(self, *args: object, **kwargs: object) -> None:
                """Allow constructing with any httpx kwargs."""

            async def __aenter__(self) -> Self:
                """Enter async context manager."""
                return self

            async def __aexit__(
                self,
                exc_type: type[BaseException] | None,
                exc: BaseException | None,
                tb: object,
            ) -> bool:
                """Exit async context manager."""
                del exc_type, exc, tb
                return False

            async def get(self, *args: object, **kwargs: object) -> object:
                """Raise timeout to emulate provider failure."""
                del args, kwargs
                message = "timeout"
                raise httpx.TimeoutException(message)

        monkeypatch.setattr("nodes.web_search.httpx.AsyncClient", FailingAsyncClient)

        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        web_search_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.WEB_SEARCH,
            data={"label": "Web Search", "max_results": 3},
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
            target_node_id=web_search_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=web_search_node.id,
            target_node_id=output_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "duckduckgo"}},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["status"] != ExecutionStatus.FAILED:
            pytest.fail("Expected FAILED status for web search runtime error")
        if not data.get("error"):
            pytest.fail("Expected error details for failed web search execution")

    @pytest.mark.asyncio
    async def test_input_node_count_error(self) -> None:
        """Request fails if workflow has more than one input node."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        first_input = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input 1", "format": "txt"},
        )
        second_input = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input 2", "format": "txt"},
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
            source_node_id=first_input.id,
            target_node_id=output_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=second_input.id,
            target_node_id=output_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("Expected BAD_REQUEST for invalid input node count")

    @pytest.mark.asyncio
    async def test_output_node_count_error(self) -> None:
        """Request fails if workflow has more than one output node."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        first_output = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output 1", "format": "txt"},
        )
        second_output = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output 2", "format": "txt"},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=first_output.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=second_output.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("Expected BAD_REQUEST for invalid output node count")

    @pytest.mark.asyncio
    async def test_cycle_error(self) -> None:
        """Request fails if workflow graph has a cycle."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        llm_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.LLM,
            data={
                "label": "LLM",
                "llm_provider_id": 1,
                "model": "test-model",
                "system_prompt": "",
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
            target_node_id=llm_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=llm_node.id,
            target_node_id=output_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=output_node.id,
            target_node_id=llm_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("Expected BAD_REQUEST for cyclic workflow graph")

    @pytest.mark.asyncio
    async def test_invalid_input_payload(self) -> None:
        """Request fails if input payload does not match txt contract."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
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

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": 1}},
            headers=headers,
        )

        if response.status_code != HTTPStatus.UNPROCESSABLE_ENTITY:
            pytest.fail("Expected UNPROCESSABLE_ENTITY for invalid input payload")

    @pytest.mark.asyncio
    async def test_execution_runtime_error(self) -> None:
        """Runtime execution errors are persisted as failed status."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        llm_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.LLM,
            data={
                "label": "LLM",
                "llm_provider_id": 999999,
                "model": "test-model",
                "system_prompt": "",
            },
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=llm_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=llm_node.id,
            target_node_id=output_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["status"] != ExecutionStatus.FAILED:
            pytest.fail("Expected FAILED status for runtime execution error")
        if not data["error"]:
            pytest.fail("Expected error details for failed execution")


class TestExecutionList(BaseTestCase):
    """Tests for GET /executions."""

    url = "/executions"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """List returns executions for the workflow."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        first = await ExecutionFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )
        second = await ExecutionFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )

        response = await self.client.get(
            url=self.url,
            params={"workflow_id": workflow.id},
            headers=headers,
        )

        data = await self.assert_response_list(response=response)
        ids = {item.get("id") for item in data}
        if first.id not in ids or second.id not in ids:
            pytest.fail("Expected executions to appear in list")
