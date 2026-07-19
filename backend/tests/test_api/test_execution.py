"""Execution API tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Self, cast

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from db.repositories import (
    EdgeRepository,
    ExecutionRepository,
    NodeExecutionRepository,
    NodeRepository,
    WorkflowRepository,
)
from enums import ExecutionSource, ExecutionStatus, NodeType
from exceptions import ExecutionGraphValidationError, LLMProviderConnectionError
from nodes import NodeExecutionResult
from schemas import ExecutionResponse

if TYPE_CHECKING:
    from nodes.base import NodeExecutionContext
from tests.factories import (
    EdgeFactory,
    ExecutionFactory,
    LLMProviderFactory,
    NodeFactory,
    WorkflowFactory,
)
from tests.test_api.base import BaseTestCase
from usecases import ExecutionUsecase

# The mocked Ollama LLM node reports 12 prompt + 4 completion tokens.
_EXPECTED_LLM_TOTAL_TOKENS = 16


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
    async def test_oversized_input_rejected(self) -> None:
        """Input text over the length cap is rejected with a validation error."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "input_data": {"value": "x" * 50_001},
            },
            headers=headers,
        )

        if response.status_code != HTTPStatus.UNPROCESSABLE_ENTITY:
            pytest.fail(f"Expected a validation error, got {response.status_code}")

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
                    "prompt_eval_count": 12,
                    "eval_count": 4,
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
        # Non-streaming worker path (no token publisher) captures usage from
        # the chat response and aggregates it onto the execution.
        if result.total_tokens != _EXPECTED_LLM_TOTAL_TOKENS:
            pytest.fail(
                f"Expected {_EXPECTED_LLM_TOTAL_TOKENS} total tokens, "
                f"got {result.total_tokens}"
            )
        await self._assert_usage_recorded(headers)

    async def _assert_usage_recorded(self, headers: dict) -> None:
        """Assert the finalized run is reflected in the tenant usage summary."""
        usage = await self.client.get(url="/usage", headers=headers)
        usage_data = await self.assert_response_dict(response=usage)
        if usage_data["executions"]["used"] != 1:
            pytest.fail("Usage summary should count the finalized execution")
        if usage_data["tokens"]["used"] != _EXPECTED_LLM_TOTAL_TOKENS:
            pytest.fail("Usage summary should sum the run's tokens")

    @pytest.mark.asyncio
    async def test_ok_with_web_search_node(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Execution succeeds with web search node in the path."""

        class DummyResponse:
            """Dummy HTTP response for web search tests."""

            status_code = HTTPStatus.OK
            text = (
                "<table>"
                '<tr class="result-sponsored"><td>'
                '<a rel="nofollow" '
                'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fads.example" '
                "class='result-link'>Sponsored Ad Result</a>"
                "</td></tr>"
                "<tr><td>"
                '<a rel="nofollow" '
                'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fduckduckgo.com" '
                "class='result-link'>DuckDuckGo</a>"
                "</td></tr>"
                "<tr><td class='result-snippet'>"
                "DuckDuckGo is a privacy-focused search engine."
                "</td></tr></table>"
            )

            def raise_for_status(self) -> None:
                """Keep successful status."""

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
        if not isinstance(output_value, str) or "Sponsored Ad Result" in output_value:
            pytest.fail("Sponsored results should be filtered out of web search output")

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

    @pytest.mark.asyncio
    async def test_filters_by_multiple_sources(self) -> None:
        """Repeated ?source= params match any of the given sources (IN, not =)."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        manual = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source=ExecutionSource.MANUAL,
        )
        telegram = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source=ExecutionSource.TELEGRAM,
        )
        schedule = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source=ExecutionSource.SCHEDULE,
        )

        response = await self.client.get(
            url=self.url,
            params={
                "workflow_id": workflow.id,
                "source": ["telegram", "schedule"],
            },
            headers=headers,
        )

        data = await self.assert_response_list(response=response)
        ids = {item.get("id") for item in data}
        if manual.id in ids:
            pytest.fail("Manual execution should not match a telegram+schedule filter")
        if telegram.id not in ids or schedule.id not in ids:
            pytest.fail("Telegram and schedule executions should both match")


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

        # Captured before run_execution: a BaseError failure rolls back the
        # shared test session, which expires already-loaded ORM objects like
        # llm_node, so its attributes must be read before that point.
        llm_node_id = llm_node.id

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
        if failed[0]["node_id"] != llm_node_id:
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

    @pytest.mark.asyncio
    async def test_oversized_node_output_truncated_in_storage(self) -> None:
        """A node's persisted output is capped, but the final answer isn't."""
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
        code_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.CODE_TRANSFORM,
            data={"label": "Code", "code": "output = input * 60000"},
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
            target_node_id=code_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=code_node.id,
            target_node_id=output_node.id,
        )

        run_response = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow.id, "input_data": {"value": "x"}},
            headers=headers,
        )
        execution = await self.assert_response_dict(response=run_response)
        result = await run_execution(self.session, execution["id"])

        # The full, untruncated answer still reaches the final execution output.
        full_length = 60000
        if not result.output_data or len(result.output_data["value"]) != full_length:
            pytest.fail("Final execution output must not be truncated")

        response = await self.client.get(
            url=f"/executions/{execution['id']}/nodes", headers=headers
        )
        data = await self.assert_response_list(response=response)
        code_result = next(item for item in data if item["node_id"] == code_node.id)

        max_stored_chars = 50_000
        if len(code_result["output"]) > max_stored_chars + 100:
            pytest.fail("Persisted node output should be capped")
        if "truncated" not in code_result["output"]:
            pytest.fail("Truncated output should carry a visible marker")


class TestExecutionCondition(BaseTestCase):
    """Tests for Condition/Router branching and skip propagation."""

    async def _build_branching_workflow(self, user: dict) -> dict[str, int]:
        """Build input -> condition -> {true, false} template branches -> output."""
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        condition_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.CONDITION,
            data={
                "label": "Condition",
                "condition_type": "contains",
                "value": "yes",
                "case_sensitive": "false",
            },
        )
        true_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.TEMPLATE,
            data={"label": "True branch", "template": "TRUE:{{input}}"},
        )
        false_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.TEMPLATE,
            data={"label": "False branch", "template": "FALSE:{{input}}"},
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
            target_node_id=condition_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=condition_node.id,
            target_node_id=true_node.id,
            source_handle="true",
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=condition_node.id,
            target_node_id=false_node.id,
            source_handle="false",
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=true_node.id,
            target_node_id=output_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=false_node.id,
            target_node_id=output_node.id,
        )
        return {
            "workflow_id": workflow.id,
            "true_node_id": true_node.id,
            "false_node_id": false_node.id,
        }

    async def _run_and_get_node_results(
        self, headers: dict, workflow_id: int, input_value: str
    ) -> tuple[dict, list[dict]]:
        """Run the workflow and return the execution plus its node results."""
        run_response = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": input_value}},
            headers=headers,
        )
        created = await self.assert_response_dict(response=run_response)
        execution = await run_execution(self.session, created["id"])
        nodes_response = await self.client.get(
            url=f"/executions/{execution.id}/nodes", headers=headers
        )
        nodes = await self.assert_response_list(response=nodes_response)
        return execution.model_dump(mode="json"), nodes

    @pytest.mark.asyncio
    async def test_matching_condition_runs_true_branch_and_skips_false(self) -> None:
        """A matching condition executes the true branch and skips the false one."""
        user, headers = await self.create_user_and_get_token()
        ids = await self._build_branching_workflow(user)

        execution, nodes = await self._run_and_get_node_results(
            headers=headers, workflow_id=ids["workflow_id"], input_value="yes please"
        )

        if execution["status"] != ExecutionStatus.SUCCESS:
            pytest.fail("Execution with a live path to output should succeed")
        if execution["output_data"]["value"] != "TRUE:yes please":
            pytest.fail("Output should carry only the true branch's text")

        by_node = {item["node_id"]: item for item in nodes}
        if by_node[ids["true_node_id"]]["status"] != ExecutionStatus.SUCCESS:
            pytest.fail("True branch should have run successfully")
        if by_node[ids["false_node_id"]]["status"] != ExecutionStatus.SKIPPED:
            pytest.fail("False branch should have been skipped")
        if by_node[ids["false_node_id"]]["output"] is not None:
            pytest.fail("A skipped node should not have an output")

    @pytest.mark.asyncio
    async def test_non_matching_condition_runs_false_branch_and_skips_true(
        self,
    ) -> None:
        """A non-matching condition executes the false branch and skips true."""
        user, headers = await self.create_user_and_get_token()
        ids = await self._build_branching_workflow(user)

        execution, nodes = await self._run_and_get_node_results(
            headers=headers, workflow_id=ids["workflow_id"], input_value="nope"
        )

        if execution["status"] != ExecutionStatus.SUCCESS:
            pytest.fail("Execution with a live path to output should succeed")
        if execution["output_data"]["value"] != "FALSE:nope":
            pytest.fail("Output should carry only the false branch's text")

        by_node = {item["node_id"]: item for item in nodes}
        if by_node[ids["false_node_id"]]["status"] != ExecutionStatus.SUCCESS:
            pytest.fail("False branch should have run successfully")
        if by_node[ids["true_node_id"]]["status"] != ExecutionStatus.SKIPPED:
            pytest.fail("True branch should have been skipped")


class TestExecutionLoop(BaseTestCase):
    """Tests for the Loop node's recursive body execution."""

    url = "/executions"

    async def _build_list_loop_workflow(self, user: dict) -> dict[str, int]:
        """Build Input -> Loop(list) -> Output; body maps LOOP_INPUT via Template."""
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        loop_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.LOOP,
            data={"label": "Loop", "mode": "list"},
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        loop_input = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.LOOP_INPUT,
            data={"label": "Loop Input"},
            parent_node_id=loop_node.id,
        )
        transform = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.TEMPLATE,
            data={"label": "Wrap", "template": "[{{input}}]"},
            parent_node_id=loop_node.id,
        )
        loop_output = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.LOOP_OUTPUT,
            data={"label": "Loop Output"},
            parent_node_id=loop_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=loop_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=loop_node.id,
            target_node_id=output_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=loop_input.id,
            target_node_id=transform.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=transform.id,
            target_node_id=loop_output.id,
        )
        return {
            "workflow_id": workflow.id,
            "loop_node_id": loop_node.id,
            "loop_input_id": loop_input.id,
            "transform_id": transform.id,
            "loop_output_id": loop_output.id,
        }

    async def _build_condition_loop_workflow(
        self, user: dict, *, stop_value: str
    ) -> dict[str, int]:
        """Build Input -> Loop(condition) -> Output; body appends 'x' each pass."""
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        loop_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.LOOP,
            data={
                "label": "Loop",
                "mode": "condition",
                "condition_type": "contains",
                "value": stop_value,
                "case_sensitive": "false",
            },
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        loop_input = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.LOOP_INPUT,
            data={"label": "Loop Input"},
            parent_node_id=loop_node.id,
        )
        transform = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.CODE_TRANSFORM,
            data={"label": "Append x", "code": "output = input + 'x'"},
            parent_node_id=loop_node.id,
        )
        loop_output = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.LOOP_OUTPUT,
            data={"label": "Loop Output"},
            parent_node_id=loop_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=loop_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=loop_node.id,
            target_node_id=output_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=loop_input.id,
            target_node_id=transform.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=transform.id,
            target_node_id=loop_output.id,
        )
        return {
            "workflow_id": workflow.id,
            "loop_node_id": loop_node.id,
            "loop_input_id": loop_input.id,
            "transform_id": transform.id,
            "loop_output_id": loop_output.id,
        }

    async def _run_and_get_node_results(
        self, headers: dict, workflow_id: int, input_value: str
    ) -> tuple[dict, list[dict]]:
        """Run the workflow and return the execution plus its node results."""
        run_response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow_id, "input_data": {"value": input_value}},
            headers=headers,
        )
        created = await self.assert_response_dict(response=run_response)
        execution = await run_execution(self.session, created["id"])
        nodes_response = await self.client.get(
            url=f"/executions/{execution.id}/nodes", headers=headers
        )
        nodes = await self.assert_response_list(response=nodes_response)
        return execution.model_dump(mode="json"), nodes

    @pytest.mark.asyncio
    async def test_list_mode_maps_over_array_and_collects_results(self) -> None:
        """List mode runs the body once per element and aggregates into JSON."""
        user, headers = await self.create_user_and_get_token()
        ids = await self._build_list_loop_workflow(user)

        execution, nodes = await self._run_and_get_node_results(
            headers=headers,
            workflow_id=ids["workflow_id"],
            input_value='["a", "b", "c"]',
        )

        if execution["status"] != ExecutionStatus.SUCCESS:
            pytest.fail(f"Execution should succeed, got {execution}")
        if execution["output_data"]["value"] != '["[a]", "[b]", "[c]"]':
            pytest.fail(
                f"Expected mapped+collected JSON array, got "
                f"{execution['output_data']['value']}"
            )

        transform_rows = sorted(
            (item for item in nodes if item["node_id"] == ids["transform_id"]),
            key=lambda item: item["iteration"],
        )
        if [item["iteration"] for item in transform_rows] != [0, 1, 2]:
            pytest.fail(f"Expected iterations 0,1,2 for the body node, got {nodes}")
        if [item["output"] for item in transform_rows] != ["[a]", "[b]", "[c]"]:
            pytest.fail("Each iteration's transform output should match its element")

        loop_row = next(
            item for item in nodes if item["node_id"] == ids["loop_node_id"]
        )
        if loop_row["iteration"] is not None:
            pytest.fail("The Loop node's own row should have iteration=None")

    @pytest.mark.asyncio
    async def test_list_mode_truncates_past_the_iteration_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A list longer than the cap runs only the first N elements."""
        monkeypatch.setattr(
            "usecases.execution.ExecutionUsecase._max_loop_iterations", 2
        )
        user, headers = await self.create_user_and_get_token()
        ids = await self._build_list_loop_workflow(user)

        execution, nodes = await self._run_and_get_node_results(
            headers=headers,
            workflow_id=ids["workflow_id"],
            input_value='["a", "b", "c"]',
        )

        if execution["status"] != ExecutionStatus.SUCCESS:
            pytest.fail(f"Execution should succeed, got {execution}")
        output = execution["output_data"]["value"]
        if '["[a]", "[b]"]' not in output or "truncated" not in output:
            pytest.fail(f"Expected a truncated-with-marker output, got {output}")

        transform_iterations = {
            item["iteration"]
            for item in nodes
            if item["node_id"] == ids["transform_id"]
        }
        if transform_iterations != {0, 1}:
            pytest.fail(f"Only the first 2 iterations should have run, got {nodes}")

    @pytest.mark.asyncio
    async def test_condition_mode_iterates_until_condition_matches(self) -> None:
        """Condition mode re-runs the body until the stop condition matches."""
        user, headers = await self.create_user_and_get_token()
        ids = await self._build_condition_loop_workflow(user, stop_value="xxx")

        execution, nodes = await self._run_and_get_node_results(
            headers=headers, workflow_id=ids["workflow_id"], input_value=""
        )

        if execution["status"] != ExecutionStatus.SUCCESS:
            pytest.fail(f"Execution should succeed, got {execution}")
        if execution["output_data"]["value"] != "xxx":
            pytest.fail(
                f"Expected the loop to stop once 'xxx' appeared, got "
                f"{execution['output_data']['value']}"
            )

        transform_iterations = sorted(
            item["iteration"]
            for item in nodes
            if item["node_id"] == ids["transform_id"]
        )
        if transform_iterations != [0, 1, 2]:
            pytest.fail(f"Expected exactly 3 iterations (0,1,2), got {nodes}")

    @pytest.mark.asyncio
    async def test_condition_mode_stops_at_cap_without_failing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A condition that never matches hard-stops at the cap, not a failure."""
        monkeypatch.setattr(
            "usecases.execution.ExecutionUsecase._max_loop_iterations", 3
        )
        user, headers = await self.create_user_and_get_token()
        ids = await self._build_condition_loop_workflow(user, stop_value="never")

        execution, nodes = await self._run_and_get_node_results(
            headers=headers, workflow_id=ids["workflow_id"], input_value=""
        )

        if execution["status"] != ExecutionStatus.SUCCESS:
            pytest.fail(
                f"Hitting the iteration cap should not fail the execution, got "
                f"{execution}"
            )
        output = execution["output_data"]["value"]
        if "stopped" not in output or "iteration cap" not in output:
            pytest.fail(f"Expected a stopped-by-cap marker in the output, got {output}")

        transform_iterations = {
            item["iteration"]
            for item in nodes
            if item["node_id"] == ids["transform_id"]
        }
        if transform_iterations != {0, 1, 2}:
            pytest.fail(f"Expected exactly 3 capped iterations, got {nodes}")


class TestCallWorkflowExecution(BaseTestCase):
    """Inline execution of a referenced workflow."""

    url = "/executions"

    async def _build_passthrough_graph(
        self, workflow_id: int, middle: tuple[NodeType, dict] | None = None
    ) -> tuple[int, int, int | None]:
        """Build Input -> optional middle -> Output and return node IDs."""
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow_id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        middle_node = None
        if middle is not None:
            middle_node = await NodeFactory.create_async(
                session=self.session,
                workflow_id=workflow_id,
                type=middle[0],
                data=middle[1],
            )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow_id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow_id,
            source_node_id=input_node.id,
            target_node_id=(middle_node.id if middle_node else output_node.id),
        )
        if middle_node is not None:
            await EdgeFactory.create_async(
                session=self.session,
                workflow_id=workflow_id,
                source_node_id=middle_node.id,
                target_node_id=output_node.id,
            )
        return input_node.id, output_node.id, middle_node.id if middle_node else None

    @pytest.mark.asyncio
    async def test_passes_input_through_called_workflow(self) -> None:
        """The target graph receives parent text and returns its Output."""
        user, headers = await self.create_user_and_get_token()
        target = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        await self._build_passthrough_graph(
            target.id,
            middle=(
                NodeType.TEMPLATE,
                {"label": "Wrap", "template": "called({{input}})"},
            ),
        )
        parent = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        _, _, call_node_id = await self._build_passthrough_graph(
            parent.id,
            middle=(
                NodeType.CALL_WORKFLOW,
                {"label": "Reuse", "target_workflow_id": target.id},
            ),
        )

        response = await self.client.post(
            self.url,
            json={"workflow_id": parent.id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        created = await self.assert_response_dict(response=response)
        execution = await run_execution(self.session, created["id"])

        if execution.status is not ExecutionStatus.SUCCESS:
            pytest.fail(f"Call Workflow execution failed: {execution.error}")
        if execution.output_data != {"value": "called(hello)"}:
            pytest.fail("Called workflow output was not returned to the parent")
        results = await NodeExecutionRepository().get_all(
            session=self.session, execution_id=execution.id
        )
        if call_node_id is None or not any(
            result.node_id == call_node_id and result.output == "called(hello)"
            for result in results
        ):
            pytest.fail("Call Workflow node result was not recorded")

    @pytest.mark.asyncio
    async def test_queued_run_pins_called_workflow_graph(self) -> None:
        """A queued run keeps the target graph captured at creation time."""
        user, headers = await self.create_user_and_get_token()
        target = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        _, _, template_node_id = await self._build_passthrough_graph(
            target.id,
            middle=(
                NodeType.TEMPLATE,
                {"label": "Wrap", "template": "v1({{input}})"},
            ),
        )
        parent = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        await self._build_passthrough_graph(
            parent.id,
            middle=(
                NodeType.CALL_WORKFLOW,
                {"label": "Reuse", "target_workflow_id": target.id},
            ),
        )

        response = await self.client.post(
            self.url,
            json={"workflow_id": parent.id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        created = await self.assert_response_dict(response=response)
        if template_node_id is None:
            pytest.fail("Expected the target workflow to contain a template node")
        await NodeRepository().update_by(
            session=self.session,
            data={"data": {"label": "Wrap", "template": "v2({{input}})"}},
            id=template_node_id,
        )
        await WorkflowRepository().delete_by(session=self.session, id=target.id)

        execution = await run_execution(self.session, created["id"])
        if execution.status is not ExecutionStatus.SUCCESS:
            pytest.fail(f"Pinned Call Workflow execution failed: {execution.error}")
        if execution.output_data != {"value": "v1(hello)"}:
            pytest.fail("Queued run did not use the snapshotted target graph")

    @pytest.mark.asyncio
    async def test_recursive_call_fails_with_clear_error(self) -> None:
        """An indirect A -> B -> A cycle is rejected before enqueueing."""
        user, headers = await self.create_user_and_get_token()
        first = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        second = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        await self._build_passthrough_graph(
            first.id,
            middle=(
                NodeType.CALL_WORKFLOW,
                {"label": "Call B", "target_workflow_id": second.id},
            ),
        )
        await self._build_passthrough_graph(
            second.id,
            middle=(
                NodeType.CALL_WORKFLOW,
                {"label": "Call A", "target_workflow_id": first.id},
            ),
        )
        response = await self.client.post(
            self.url,
            json={"workflow_id": first.id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("Recursive workflow call should be rejected")
        detail = str(response.json().get("detail", ""))
        if "Recursive workflow call detected" not in detail:
            pytest.fail(f"Cycle error was not clear: {detail}")


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

        async def flaky(*args: object, **kwargs: object) -> NodeExecutionResult:
            """Fail on the first call, then succeed."""
            del args, kwargs
            calls["count"] += 1
            if calls["count"] == 1:
                raise LLMProviderConnectionError(message="temporary blip")
            return NodeExecutionResult(output="ok")

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
    async def test_retry_publishes_token_reset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A node retry signals clients to discard its streamed text first."""
        calls = {"count": 0}

        async def flaky(*args: object, **kwargs: object) -> NodeExecutionResult:
            """Fail on the first call, then succeed."""
            del args, kwargs
            calls["count"] += 1
            if calls["count"] == 1:
                raise LLMProviderConnectionError(message="temporary blip")
            return NodeExecutionResult(output="ok")

        monkeypatch.setattr("nodes.registry.NodeHandlerRegistry.execute", flaky)
        monkeypatch.setattr(
            "usecases.execution.ExecutionUsecase._retry_delay",
            lambda _self, attempt: 0.0 * attempt,
        )

        user, headers = await self.create_user_and_get_token()
        workflow_id = await self._create_input_output_workflow(user)

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow_id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        created = await self.assert_response_dict(response=response)

        reset_calls: list[tuple[int, int]] = []

        async def token_reset_publisher(exec_id: int, node_id: int) -> None:
            reset_calls.append((exec_id, node_id))

        result = await ExecutionUsecase().run_execution(
            session=self.session,
            execution_id=created["id"],
            token_reset_publisher=token_reset_publisher,
        )

        if result.status != ExecutionStatus.SUCCESS:
            pytest.fail("Execution should succeed after a retryable failure")
        if len(reset_calls) != 1:
            pytest.fail(f"Expected exactly one reset signal, got {reset_calls}")
        if reset_calls[0][0] != created["id"]:
            pytest.fail("Reset signal carried the wrong execution ID")

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
        stale_started = datetime.now(tz=UTC) - timedelta(hours=2)
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
    async def test_recent_heartbeat_protects_a_long_running_execution(self) -> None:
        """An old start time doesn't reap a run whose heartbeat is recent."""
        user, _ = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        old_start = datetime.now(tz=UTC) - timedelta(hours=2)
        still_active = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            status=ExecutionStatus.RUNNING,
            started_at=old_start,
            heartbeat_at=datetime.now(tz=UTC),
        )
        active_id = still_active.id

        reaped = await ExecutionUsecase().reap_stuck_executions(session=self.session)

        if reaped != 0:
            pytest.fail("A run with a fresh heartbeat should not be reaped")

        self.session.expire_all()
        after = await ExecutionRepository().get_by(session=self.session, id=active_id)
        if after is None or after.status != ExecutionStatus.RUNNING:
            pytest.fail("Long-running-but-active execution should stay RUNNING")

    @pytest.mark.asyncio
    async def test_reenqueues_only_stale_created_executions(self) -> None:
        """A CREATED execution stuck past the timeout is re-enqueued once."""
        user, _ = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        stale_started = datetime.now(tz=UTC) - timedelta(seconds=300)
        stale = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            status=ExecutionStatus.CREATED,
            started_at=stale_started,
        )
        fresh = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            status=ExecutionStatus.CREATED,
        )
        stale_id = stale.id
        fresh_id = fresh.id

        re_enqueued: list[int] = []

        async def re_enqueue(execution_id: int) -> None:
            re_enqueued.append(execution_id)

        reaped = await ExecutionUsecase().reap_stuck_executions(
            session=self.session, re_enqueue=re_enqueue
        )

        expected_reaped = 1
        if reaped != expected_reaped:
            pytest.fail("Expected exactly one stale CREATED execution to be reaped")
        if re_enqueued != [stale_id]:
            pytest.fail("re_enqueue should be called once with the stale execution")
        if fresh_id in re_enqueued:
            pytest.fail("A fresh CREATED execution should not be re-enqueued")

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

    @pytest.mark.asyncio
    async def test_heartbeat_bumped_as_nodes_complete(self) -> None:
        """Running a workflow advances the execution's heartbeat."""
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

        run_response = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        execution = await self.assert_response_dict(response=run_response)
        await run_execution(self.session, execution["id"])

        self.session.expire_all()
        after = await ExecutionRepository().get_by(
            session=self.session, id=execution["id"]
        )
        if after is None or after.heartbeat_at is None:
            pytest.fail("Expected heartbeat_at to be set after nodes completed")


@pytest.mark.committed_db
class TestExecutionParallel(BaseTestCase):
    """Tests for concurrent execution of independent graph branches."""

    @pytest.mark.asyncio
    async def test_independent_branches_run_concurrently(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two sibling branches of a diamond graph overlap in time."""

        async def slow_execute(*args: object, **kwargs: object) -> NodeExecutionResult:
            """Simulate slow node work so concurrent branches overlap."""
            del args, kwargs
            await asyncio.sleep(0.3)
            return NodeExecutionResult(output="ok")

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

    async def _build_diamond(self, user: dict) -> dict[str, int]:
        """Build Input -> {A, B} -> Output and return node IDs by label."""
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
        return {
            "workflow": workflow.id,
            "input": input_node.id,
            "a": branch_a.id,
            "b": branch_b.id,
            "output": output_node.id,
        }

    @pytest.mark.asyncio
    async def test_simultaneous_wave_failures_are_aggregated(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two nodes failing in the same wave both appear in the error."""

        async def fail_ab(*args: object, **kwargs: object) -> NodeExecutionResult:
            """Fail nodes A and B; succeed for everything else."""
            del args
            context = cast("NodeExecutionContext", kwargs["context"])
            label = context.node_data.get("label")
            if label in {"A", "B"}:
                message = f"{label} broke"
                raise ExecutionGraphValidationError(message=message)
            return NodeExecutionResult(output="ok")

        monkeypatch.setattr("nodes.registry.NodeHandlerRegistry.execute", fail_ab)

        user, _ = await self.create_user_and_get_token()
        ids = await self._build_diamond(user)
        execution = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=ids["workflow"],
            status=ExecutionStatus.CREATED,
            input_data={"value": "hello"},
        )
        execution_id = execution.id

        factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        result = await ExecutionUsecase().run_execution(
            session=self.session, execution_id=execution_id, session_factory=factory
        )

        if result.status != ExecutionStatus.FAILED:
            pytest.fail("Execution with two failing nodes should be FAILED")
        error = result.error or ""
        if "A broke" not in error or "B broke" not in error:
            pytest.fail(f"Expected both node failures in the error, got: {error!r}")

    @pytest.mark.asyncio
    async def test_unreached_node_marked_skipped_after_wave_failure(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A node in a later wave gets a SKIPPED row, not no row at all."""

        async def fail_a(*args: object, **kwargs: object) -> NodeExecutionResult:
            """Fail node A only; succeed for everything else."""
            del args
            context = cast("NodeExecutionContext", kwargs["context"])
            if context.node_data.get("label") == "A":
                message = "A broke"
                raise ExecutionGraphValidationError(message=message)
            return NodeExecutionResult(output="ok")

        monkeypatch.setattr("nodes.registry.NodeHandlerRegistry.execute", fail_a)

        user, _ = await self.create_user_and_get_token()
        ids = await self._build_diamond(user)
        execution = await ExecutionFactory.create_async(
            session=self.session,
            workflow_id=ids["workflow"],
            status=ExecutionStatus.CREATED,
            input_data={"value": "hello"},
        )
        execution_id = execution.id

        factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        result = await ExecutionUsecase().run_execution(
            session=self.session, execution_id=execution_id, session_factory=factory
        )
        if result.status != ExecutionStatus.FAILED:
            pytest.fail("Execution with a failing node should be FAILED")

        self.session.expire_all()
        rows = await NodeExecutionRepository().get_all(
            session=self.session, execution_id=execution_id
        )
        by_node = {row.node_id: row for row in rows}
        output_row = by_node.get(ids["output"])
        if output_row is None or output_row.status != ExecutionStatus.SKIPPED:
            pytest.fail("Unreached Output node should be marked SKIPPED")


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


class TestExecutionVersioning(BaseTestCase):
    """Tests for workflow-version snapshotting on execution create/run."""

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

    async def _list_versions(
        self, workflow_id: int, headers: dict
    ) -> list[dict[str, Any]]:
        """Fetch a workflow's version snapshots via the API."""
        response = await self.client.get(
            url=f"/workflows/{workflow_id}/versions", headers=headers
        )
        return await self.assert_response_list(response=response)

    @pytest.mark.asyncio
    async def test_create_pins_and_dedupes_snapshot(self) -> None:
        """Two runs of an unchanged graph share a single deduped version."""
        user, headers = await self.create_user_and_get_token()
        workflow_id = await self._create_input_output_workflow(user)

        first = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": "a"}},
            headers=headers,
        )
        first_data = await self.assert_response_dict(response=first)
        second = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": "b"}},
            headers=headers,
        )
        second_data = await self.assert_response_dict(response=second)

        if first_data["version_id"] is None:
            pytest.fail("Execution should be pinned to a version snapshot")
        if first_data["version_id"] != second_data["version_id"]:
            pytest.fail("Unchanged graph should dedupe to the same version")

        versions = await self._list_versions(workflow_id, headers)
        if len(versions) != 1:
            pytest.fail("Unchanged graph should produce exactly one version")
        if versions[0]["version"] != 1:
            pytest.fail("First snapshot should be version number 1")

    @pytest.mark.asyncio
    async def test_graph_change_creates_new_version(self) -> None:
        """Editing the graph between runs bumps the version number."""
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
        direct_edge = await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=output_node.id,
        )
        workflow_id = workflow.id

        first = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": "a"}},
            headers=headers,
        )
        first_data = await self.assert_response_dict(response=first)

        # Rewire the live graph into input -> template -> output (still valid).
        await EdgeRepository().delete_by(session=self.session, id=direct_edge.id)
        template_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow_id,
            type=NodeType.TEMPLATE,
            data={"label": "Template", "template": "{{input}}"},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow_id,
            source_node_id=input_node.id,
            target_node_id=template_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow_id,
            source_node_id=template_node.id,
            target_node_id=output_node.id,
        )

        second = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": "b"}},
            headers=headers,
        )
        second_data = await self.assert_response_dict(response=second)

        if first_data["version_id"] == second_data["version_id"]:
            pytest.fail("Changed graph should produce a distinct version")

        versions = await self._list_versions(workflow_id, headers)
        numbers = sorted(int(version["version"]) for version in versions)
        if numbers != [1, 2]:
            pytest.fail("Changed graph should produce versions numbered 1 and 2")

    @pytest.mark.asyncio
    async def test_run_pinned_version_is_reproducible(self) -> None:
        """A pinned execution reproduces its snapshot after the live graph is edited."""
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
        template_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.TEMPLATE,
            data={"label": "Template", "template": "{{input}} v1"},
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
            target_node_id=template_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=template_node.id,
            target_node_id=output_node.id,
        )
        workflow_id = workflow.id

        first = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        first_data = await self.assert_response_dict(response=first)
        pinned_version_id = first_data["version_id"]

        # Edit the live template so a fresh run would render differently. Nodes keep
        # their IDs, so the snapshot rerun still records node executions cleanly.
        await NodeRepository().update_by(
            session=self.session,
            data={"data": {"label": "Template", "template": "{{input}} v2"}},
            id=template_node.id,
        )

        # Re-run the original pinned version explicitly.
        rerun = await self.client.post(
            url="/executions",
            json={
                "workflow_id": workflow_id,
                "input_data": {"value": "hello"},
                "version_id": pinned_version_id,
            },
            headers=headers,
        )
        rerun_data = await self.assert_response_dict(response=rerun)
        if rerun_data["version_id"] != pinned_version_id:
            pytest.fail("Explicit version_id should pin the execution to it")

        result = await run_execution(self.session, rerun_data["id"])
        if result.status != ExecutionStatus.SUCCESS:
            pytest.fail("Pinned version should run to success")
        if result.output_data != {"value": "hello v1"}:
            pytest.fail("Pinned version should reproduce the v1 snapshot output")

    @pytest.mark.asyncio
    async def test_run_pinned_version_survives_deleted_node(self) -> None:
        """Rerunning a pinned version still records results after a node is deleted."""
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
        template_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.TEMPLATE,
            data={"label": "Template", "template": "{{input}}"},
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
            target_node_id=template_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=template_node.id,
            target_node_id=output_node.id,
        )
        workflow_id = workflow.id
        template_node_id = template_node.id

        first = await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        first_data = await self.assert_response_dict(response=first)
        pinned_version_id = first_data["version_id"]

        # Delete the template node from the live graph (not just edit it) —
        # the pinned snapshot still references its now-nonexistent ID.
        await NodeRepository().delete_by(session=self.session, id=template_node_id)

        rerun = await self.client.post(
            url="/executions",
            json={
                "workflow_id": workflow_id,
                "input_data": {"value": "hello"},
                "version_id": pinned_version_id,
            },
            headers=headers,
        )
        rerun_data = await self.assert_response_dict(response=rerun)

        result = await run_execution(self.session, rerun_data["id"])
        if result.status != ExecutionStatus.SUCCESS:
            pytest.fail("Pinned version should still run after its node is deleted")

        node_executions = await NodeExecutionRepository().get_all(
            session=self.session, execution_id=result.id, node_id=template_node_id
        )
        if len(node_executions) != 1:
            pytest.fail("The deleted node's result should still be recorded")
        recorded = node_executions[0]
        if recorded.node_type != NodeType.TEMPLATE:
            pytest.fail("Node type should be denormalized even after node deletion")
        if recorded.node_label != "Template":
            pytest.fail("Node label should be denormalized even after node deletion")

    @pytest.mark.asyncio
    async def test_unknown_version_id_is_rejected(self) -> None:
        """Requesting a non-existent version_id fails fast."""
        user, headers = await self.create_user_and_get_token()
        workflow_id = await self._create_input_output_workflow(user)

        response = await self.client.post(
            url="/executions",
            json={
                "workflow_id": workflow_id,
                "input_data": {"value": "x"},
                "version_id": 999_999,
            },
            headers=headers,
        )
        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Unknown version_id should return NOT_FOUND")

    @pytest.mark.asyncio
    async def test_other_user_cannot_list_versions(self) -> None:
        """Version listing is scoped to the workflow owner."""
        owner, owner_headers = await self.create_user_and_get_token()
        workflow_id = await self._create_input_output_workflow(owner)
        await self.client.post(
            url="/executions",
            json={"workflow_id": workflow_id, "input_data": {"value": "a"}},
            headers=owner_headers,
        )

        _, other_headers = await self.create_user_and_get_token()
        response = await self.client.get(
            url=f"/workflows/{workflow_id}/versions", headers=other_headers
        )
        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Expected NOT_FOUND listing another user's versions")
