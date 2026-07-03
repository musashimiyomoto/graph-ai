"""Execution API tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Self

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from db.repositories import ExecutionRepository, NodeExecutionRepository
from enums import ExecutionStatus, NodeType
from exceptions import ExecutionGraphValidationError, LLMProviderConnectionError
from schemas import ExecutionResponse
from tests.factories import (
    EdgeFactory,
    ExecutionFactory,
    LLMProviderFactory,
    NodeFactory,
    WorkflowFactory,
)
from tests.test_api.base import BaseTestCase
from usecases import ExecutionUsecase


async def run_execution(session: AsyncSession, execution_id: int) -> ExecutionResponse:
    """Run a queued execution to completion (worker stand-in for tests).

    Args:
        session: The test session.
        execution_id: The execution to run.

    Returns:
        The finalized execution.

    """
    return await ExecutionUsecase().run_execution(
        session=session, execution_id=execution_id
    )


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
        if data["status"] != ExecutionStatus.CREATED:
            pytest.fail("Queued execution should start in CREATED state")

        result = await run_execution(self.session, data["id"])
        if result.status != ExecutionStatus.SUCCESS:
            pytest.fail("Execution status did not match success state")
        if result.output_data != {"value": "hello"}:
            pytest.fail("Execution output did not match expected value")
        if result.error is not None:
            pytest.fail("Execution error should be null for success")

    @pytest.mark.asyncio
    async def test_fan_in_merge_order_is_deterministic(self) -> None:
        """Multiple parents merge in stable node-id order, not edge-insert order."""
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
        first = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.TEMPLATE,
            data={"label": "A", "template": "A"},
        )
        second = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.TEMPLATE,
            data={"label": "B", "template": "B"},
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        for source, target in (
            (input_node.id, first.id),
            (input_node.id, second.id),
        ):
            await EdgeFactory.create_async(
                session=self.session,
                workflow_id=workflow.id,
                source_node_id=source,
                target_node_id=target,
            )
        # Insert the higher-id parent's edge first: without deterministic ordering
        # the output would merge as "B\nA".
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=second.id,
            target_node_id=output_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=first.id,
            target_node_id=output_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "x"}},
            headers=headers,
        )
        data = await self.assert_response_dict(response=response)

        result = await run_execution(self.session, data["id"])
        if result.status != ExecutionStatus.SUCCESS:
            pytest.fail("Fan-in execution should succeed")
        if result.output_data != {"value": "A\nB"}:
            pytest.fail(f"Parents merged in wrong order: {result.output_data}")

    @pytest.mark.asyncio
    async def test_ok_with_llm_node(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Execution succeeds with an LLM node, mocking the Ollama chat call."""

        class DummyResponse:
            """Dummy HTTP response for Ollama chat tests."""

            status_code = HTTPStatus.OK
            text = ""

            def raise_for_status(self) -> None:
                """Keep successful status."""

            def json(self) -> dict:
                """Return a mock Ollama chat payload."""
                return {
                    "model": "test-model",
                    "message": {"role": "assistant", "content": "hi from llm"},
                    "done": True,
                }

        class DummyAsyncClient:
            """Dummy async client that returns a fixed chat payload."""

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

            async def post(self, *args: object, **kwargs: object) -> DummyResponse:
                """Return a successful chat response."""
                del args, kwargs
                return DummyResponse()

        monkeypatch.setattr("llm.ollama.httpx.AsyncClient", DummyAsyncClient)

        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session,
            user_id=user["id"],
            base_url="http://ollama:11434",
        )
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
                "llm_provider_id": provider.id,
                "model": "test-model",
                "system_prompt": "You are a helpful assistant.",
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

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        result = await run_execution(self.session, data["id"])
        if result.status != ExecutionStatus.SUCCESS:
            pytest.fail("Execution with LLM node should succeed")
        if result.output_data != {"value": "hi from llm"}:
            pytest.fail("Execution output did not match mocked LLM content")

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
        result = await run_execution(self.session, data["id"])
        if result.status != ExecutionStatus.SUCCESS:
            pytest.fail("Execution with web search node should succeed")
        output_value = (
            result.output_data.get("value")
            if isinstance(result.output_data, dict)
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
        result = await run_execution(self.session, data["id"])
        if result.status != ExecutionStatus.FAILED:
            pytest.fail("Expected FAILED status for web search runtime error")
        if not result.error:
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
    async def test_incompatible_ports_error(self) -> None:
        """Request fails if an edge connects incompatible node ports."""
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
        # Edge feeding into the input node, which has no input port.
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=llm_node.id,
            target_node_id=input_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("Expected BAD_REQUEST for incompatible node ports")

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
        result = await run_execution(self.session, data["id"])
        if result.status != ExecutionStatus.FAILED:
            pytest.fail("Expected FAILED status for runtime execution error")
        if not result.error:
            pytest.fail("Expected error details for failed execution")

    @pytest.mark.asyncio
    async def test_execution_unexpected_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unexpected (non-domain) errors are persisted as failed, not stranded."""

        async def _raise(*args: object, **kwargs: object) -> str:
            """Emulate an unexpected runtime failure inside a node handler."""
            del args, kwargs
            message = "boom"
            raise RuntimeError(message)

        monkeypatch.setattr("nodes.registry.NodeHandlerRegistry.execute", _raise)

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
        result = await run_execution(self.session, data["id"])
        if result.status != ExecutionStatus.FAILED:
            pytest.fail("Expected FAILED status for unexpected execution error")
        if result.error != "Internal execution error":
            pytest.fail("Expected generic error message for unexpected failure")


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


class TestNodeExecutionList(BaseTestCase):
    """Tests for GET /executions/{execution_id}/nodes."""

    async def _create_workflow_with_input_output(self, user: dict) -> int:
        """Create a minimal input -> output workflow and return its ID."""
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
        return workflow.id

    @pytest.mark.asyncio
    async def test_records_node_results_on_success(self) -> None:
        """Every executed node is persisted with SUCCESS status and output."""
        user, headers = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow_with_input_output(user)

        run_response = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        execution = await self.assert_response_dict(response=run_response)
        await run_execution(self.session, execution["id"])

        response = await self.client.get(
            url=f"/executions/{execution['id']}/nodes", headers=headers
        )

        data = await self.assert_response_list(response=response)
        expected_node_count = 2
        if len(data) != expected_node_count:
            pytest.fail("Expected one node execution per node in the path")
        if any(item["status"] != ExecutionStatus.SUCCESS for item in data):
            pytest.fail("Expected all node executions to be SUCCESS")
        if not any(item["output"] == "hello" for item in data):
            pytest.fail("Expected a node execution to carry the propagated output")

    @pytest.mark.asyncio
    async def test_records_failed_node(self) -> None:
        """The failing node is persisted with FAILED status and an error."""
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
                "llm_provider_id": 999999,
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

        run_response = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        execution = await self.assert_response_dict(response=run_response)
        await run_execution(self.session, execution["id"])

        response = await self.client.get(
            url=f"/executions/{execution['id']}/nodes", headers=headers
        )

        data = await self.assert_response_list(response=response)
        failed = [item for item in data if item["status"] == ExecutionStatus.FAILED]
        if len(failed) != 1:
            pytest.fail("Expected exactly one FAILED node execution")
        if failed[0]["node_id"] != llm_node.id:
            pytest.fail("Expected the LLM node to be the failing node")
        if not failed[0]["error"]:
            pytest.fail("Expected error details on the failed node execution")

    @pytest.mark.asyncio
    async def test_other_user_cannot_read_node_results(self) -> None:
        """Node results of another user's execution are not accessible."""
        owner, owner_headers = await self.create_user_and_get_token()
        workflow_id = await self._create_workflow_with_input_output(owner)
        run_response = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": "hello"}},
            headers=owner_headers,
        )
        execution = await self.assert_response_dict(response=run_response)
        await run_execution(self.session, execution["id"])

        _, other_headers = await self.create_user_and_get_token()
        response = await self.client.get(
            url=f"/executions/{execution['id']}/nodes", headers=other_headers
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Expected NOT_FOUND when reading another user's node results")


class TestExecutionRetries(BaseTestCase):
    """Tests for node-level retries and timeouts."""

    url = "/executions"

    async def _create_input_output_workflow(self, user: dict) -> int:
        """Create a minimal input -> output workflow and return its ID."""
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
        return workflow.id

    async def _run(self, workflow_id: int, headers: dict) -> dict:
        """Trigger an execution, run it, and return the finalized body."""
        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow_id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        created = await self.assert_response_dict(response=response)
        result = await run_execution(self.session, created["id"])
        return result.model_dump(mode="json")

    @pytest.mark.asyncio
    async def test_retryable_error_succeeds_after_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A transient node failure is retried and the execution succeeds."""
        calls = {"count": 0}

        async def flaky(*args: object, **kwargs: object) -> str:
            """Fail on the first call, then succeed."""
            del args, kwargs
            calls["count"] += 1
            if calls["count"] == 1:
                raise LLMProviderConnectionError(message="temporary blip")
            return "ok"

        monkeypatch.setattr("nodes.registry.NodeHandlerRegistry.execute", flaky)
        monkeypatch.setattr(
            "usecases.execution.ExecutionUsecase._retry_delay",
            lambda _self, attempt: 0.0 * attempt,
        )

        user, headers = await self.create_user_and_get_token()
        workflow_id = await self._create_input_output_workflow(user)

        data = await self._run(workflow_id=workflow_id, headers=headers)

        if data["status"] != ExecutionStatus.SUCCESS:
            pytest.fail("Execution should succeed after a retryable failure")
        expected_calls = 3
        if calls["count"] != expected_calls:
            pytest.fail("Expected input retry (2 calls) plus output call")

    @pytest.mark.asyncio
    async def test_retryable_error_fails_after_exhausting_retries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A persistently failing node is retried then marked FAILED."""
        calls = {"count": 0}

        async def always_failing(*args: object, **kwargs: object) -> str:
            """Raise a retryable error on every call."""
            del args, kwargs
            calls["count"] += 1
            raise LLMProviderConnectionError(message="still down")

        monkeypatch.setattr(
            "nodes.registry.NodeHandlerRegistry.execute", always_failing
        )
        monkeypatch.setattr(
            "usecases.execution.ExecutionUsecase._retry_delay",
            lambda _self, attempt: 0.0 * attempt,
        )

        user, headers = await self.create_user_and_get_token()
        workflow_id = await self._create_input_output_workflow(user)

        data = await self._run(workflow_id=workflow_id, headers=headers)

        if data["status"] != ExecutionStatus.FAILED:
            pytest.fail("Execution should fail after exhausting retries")
        expected_attempts = 3
        if calls["count"] != expected_attempts:
            pytest.fail("Expected the node to be attempted exactly max-attempts times")

    @pytest.mark.asyncio
    async def test_non_retryable_error_is_not_retried(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-retryable node error fails immediately without retries."""
        calls = {"count": 0}

        async def config_error(*args: object, **kwargs: object) -> str:
            """Raise a non-retryable validation error."""
            del args, kwargs
            calls["count"] += 1
            raise ExecutionGraphValidationError(message="bad config")

        monkeypatch.setattr("nodes.registry.NodeHandlerRegistry.execute", config_error)

        user, headers = await self.create_user_and_get_token()
        workflow_id = await self._create_input_output_workflow(user)

        data = await self._run(workflow_id=workflow_id, headers=headers)

        if data["status"] != ExecutionStatus.FAILED:
            pytest.fail("Execution should fail on a non-retryable error")
        if calls["count"] != 1:
            pytest.fail("A non-retryable error must not be retried")

    @pytest.mark.asyncio
    async def test_node_timeout_marks_execution_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A node exceeding its time budget is timed out and fails the run."""

        async def hanging(*args: object, **kwargs: object) -> str:
            """Sleep past the (tiny) node timeout budget."""
            del args, kwargs
            await asyncio.sleep(1)
            return "never"

        monkeypatch.setattr("nodes.registry.NodeHandlerRegistry.execute", hanging)
        monkeypatch.setattr(
            "usecases.execution.ExecutionUsecase._node_timeout_seconds", 0.01
        )
        monkeypatch.setattr(
            "usecases.execution.ExecutionUsecase._retry_delay",
            lambda _self, attempt: 0.0 * attempt,
        )

        user, headers = await self.create_user_and_get_token()
        workflow_id = await self._create_input_output_workflow(user)

        data = await self._run(workflow_id=workflow_id, headers=headers)

        if data["status"] != ExecutionStatus.FAILED:
            pytest.fail("Execution should fail when a node times out")
        if not data["error"] or "timed out" not in data["error"].lower():
            pytest.fail("Expected a timeout error message on the failed execution")


class TestExecutionReaper(BaseTestCase):
    """Tests for reaping executions stuck in RUNNING."""

    @pytest.mark.asyncio
    async def test_reaps_only_stale_running_executions(self) -> None:
        """Old RUNNING executions are failed; recent ones are left alone."""
        user, _ = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        stale_started = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(hours=2)
        stale = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            status=ExecutionStatus.RUNNING,
            started_at=stale_started,
        )
        fresh = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            status=ExecutionStatus.RUNNING,
        )
        stale_id = stale.id
        fresh_id = fresh.id

        reaped = await ExecutionUsecase().reap_stuck_executions(session=self.session)

        expected_reaped = 1
        if reaped != expected_reaped:
            pytest.fail("Expected exactly one stuck execution to be reaped")

        self.session.expire_all()
        repository = ExecutionRepository()
        stale_after = await repository.get_by(session=self.session, id=stale_id)
        fresh_after = await repository.get_by(session=self.session, id=fresh_id)
        if stale_after is None or stale_after.status != ExecutionStatus.FAILED:
            pytest.fail("Stale RUNNING execution should be marked FAILED")
        if fresh_after is None or fresh_after.status != ExecutionStatus.RUNNING:
            pytest.fail("Recent RUNNING execution should be left untouched")

    @pytest.mark.asyncio
    async def test_status_cas_prevents_clobber(self) -> None:
        """A finalized execution cannot be re-finalized (reaper/worker anti-clobber)."""
        user, _ = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        execution = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            status=ExecutionStatus.RUNNING,
        )
        execution_id = execution.id
        repository = ExecutionRepository()

        first = await repository.update_status_if(
            session=self.session,
            execution_id=execution_id,
            expected_status=ExecutionStatus.RUNNING,
            data={"status": ExecutionStatus.SUCCESS},
        )
        second = await repository.update_status_if(
            session=self.session,
            execution_id=execution_id,
            expected_status=ExecutionStatus.RUNNING,
            data={"status": ExecutionStatus.FAILED},
        )

        if not first:
            pytest.fail("First compare-and-set on RUNNING should win")
        if second:
            pytest.fail("Second compare-and-set should not win after finalization")

        self.session.expire_all()
        after = await repository.get_by(session=self.session, id=execution_id)
        if after is None or after.status != ExecutionStatus.SUCCESS:
            pytest.fail("Finalized status must not be clobbered")


class TestExecutionParallel(BaseTestCase):
    """Tests for concurrent execution of independent graph branches."""

    @pytest.mark.asyncio
    async def test_independent_branches_run_concurrently(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two sibling branches of a diamond graph overlap in time."""

        async def slow_execute(*args: object, **kwargs: object) -> str:
            """Simulate slow node work so concurrent branches overlap."""
            del args, kwargs
            await asyncio.sleep(0.3)
            return "ok"

        monkeypatch.setattr("nodes.registry.NodeHandlerRegistry.execute", slow_execute)

        user, _ = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        branch_a = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.LLM,
            data={"label": "A"},
        )
        branch_b = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.LLM,
            data={"label": "B"},
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        for source, target in (
            (input_node, branch_a),
            (input_node, branch_b),
            (branch_a, output_node),
            (branch_b, output_node),
        ):
            await EdgeFactory.create_async(
                session=self.session,
                workflow_id=workflow.id,
                source_node_id=source.id,
                target_node_id=target.id,
            )
        execution = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            status=ExecutionStatus.CREATED,
            input_data={"value": "hello"},
        )
        execution_id = execution.id
        a_id = branch_a.id
        b_id = branch_b.id

        factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        result = await ExecutionUsecase().run_execution(
            session=self.session, execution_id=execution_id, session_factory=factory
        )
        if result.status != ExecutionStatus.SUCCESS:
            pytest.fail("Parallel diamond execution should succeed")

        self.session.expire_all()
        rows = await NodeExecutionRepository().get_all(
            session=self.session, execution_id=execution_id
        )
        by_node = {row.node_id: row for row in rows}
        first = by_node[a_id]
        second = by_node[b_id]
        first_end = first.finished_at
        second_end = second.finished_at
        if first_end is None or second_end is None:
            message = "Both branches should have finished timestamps"
            raise AssertionError(message)
        overlapped = first.started_at < second_end and second.started_at < first_end
        if not overlapped:
            pytest.fail("Independent branches did not overlap; ran serially")


class TestExecutionStream(BaseTestCase):
    """Tests for GET /executions/{execution_id}/stream (SSE)."""

    async def _create_input_output_workflow(self, user: dict) -> int:
        """Create a minimal input -> output workflow and return its ID."""
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
        return workflow.id

    @pytest.mark.asyncio
    async def test_stream_emits_terminal_status(self) -> None:
        """The stream emits an SSE frame with the terminal status and closes."""
        user, headers = await self.create_user_and_get_token()
        workflow_id = await self._create_input_output_workflow(user)

        run_response = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        created = await self.assert_response_dict(response=run_response)
        await run_execution(self.session, created["id"])

        response = await self.client.get(
            url=f"/executions/{created['id']}/stream", headers=headers
        )

        if response.status_code != HTTPStatus.OK:
            pytest.fail("Stream request should return OK")
        if not response.headers["content-type"].startswith("text/event-stream"):
            pytest.fail("Stream should use the SSE content type")
        if "data:" not in response.text or ExecutionStatus.SUCCESS not in response.text:
            pytest.fail("Stream should emit the terminal SUCCESS status")

    @pytest.mark.asyncio
    async def test_other_user_cannot_stream(self) -> None:
        """A stream for another user's execution is rejected before streaming."""
        owner, owner_headers = await self.create_user_and_get_token()
        workflow_id = await self._create_input_output_workflow(owner)
        run_response = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": "hello"}},
            headers=owner_headers,
        )
        created = await self.assert_response_dict(response=run_response)

        _, other_headers = await self.create_user_and_get_token()
        response = await self.client.get(
            url=f"/executions/{created['id']}/stream", headers=other_headers
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Expected NOT_FOUND streaming another user's execution")
