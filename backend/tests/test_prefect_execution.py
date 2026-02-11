"""Tests for Prefect workflow execution integration."""

from contextlib import AbstractAsyncContextManager

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from enums import ExecutionStatus, NodeType
from flows.prefect_execution_flow import run_workflow_execution
from integrations import LLMClientFactory
from models import Execution
from tests.factories import (
    EdgeFactory,
    ExecutionFactory,
    LLMProviderFactory,
    NodeFactory,
    UserFactory,
    WorkflowFactory,
)


class _SessionContext(AbstractAsyncContextManager[AsyncSession]):
    """Context manager returning the provided session."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize wrapper."""
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        """Return wrapped session."""
        return self._session

    async def __aexit__(self, *args: object) -> None:
        """Do nothing on exit."""
        return


@pytest.mark.asyncio
async def test_run_workflow_execution_success(
    test_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flow marks execution as success for valid input->output graph."""
    user = await UserFactory.create_async(session=test_session)
    workflow = await WorkflowFactory.create_async(
        session=test_session,
        owner_id=user.id,
    )
    input_node = await NodeFactory.create_async(
        session=test_session,
        workflow_id=workflow.id,
        type=NodeType.INPUT,
        data={"label": "Input", "format": "txt"},
    )
    output_node = await NodeFactory.create_async(
        session=test_session,
        workflow_id=workflow.id,
        type=NodeType.OUTPUT,
        data={"label": "Output", "format": "txt"},
    )
    await EdgeFactory.create_async(
        session=test_session,
        workflow_id=workflow.id,
        source_node_id=input_node.id,
        target_node_id=output_node.id,
    )
    execution = await ExecutionFactory.create_async(
        session=test_session,
        workflow_id=workflow.id,
        status=ExecutionStatus.RUNNING,
        input_data={"value": "hello"},
    )

    monkeypatch.setattr(
        "flows.prefect_execution_flow.async_session",
        lambda: _SessionContext(test_session),
    )

    await run_workflow_execution.fn(execution.id)

    loaded = await test_session.get(Execution, execution.id)
    if loaded is None:
        pytest.fail("Execution was not found after flow completion")
        return
    execution_entity = loaded
    if execution_entity.status != ExecutionStatus.SUCCESS:
        pytest.fail("Execution status was not updated to success")
    if execution_entity.output_data != {"value": "hello"}:
        pytest.fail("Execution output_data did not match expected value")
    if execution_entity.finished_at is None:
        pytest.fail("Execution finished_at was not set")


@pytest.mark.asyncio
async def test_run_workflow_execution_llm_failure(
    test_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flow marks execution as failed when LLM client raises an error."""

    class _FailingClient:
        """Client mock that fails for chat calls."""

        async def chat(self, model: str, messages: list[object]) -> object:
            """Raise runtime error."""
            del model
            del messages
            message = "LLM exploded"
            raise RuntimeError(message)

    def fake_get_client(self: LLMClientFactory, llm_provider: object) -> _FailingClient:
        """Return failing client."""
        del self
        del llm_provider
        return _FailingClient()

    monkeypatch.setattr(
        LLMClientFactory,
        "get_client",
        fake_get_client,
    )

    user = await UserFactory.create_async(session=test_session)
    workflow = await WorkflowFactory.create_async(
        session=test_session,
        owner_id=user.id,
    )
    provider = await LLMProviderFactory.create_async(
        session=test_session,
        user_id=user.id,
    )
    input_node = await NodeFactory.create_async(
        session=test_session,
        workflow_id=workflow.id,
        type=NodeType.INPUT,
        data={"label": "Input", "format": "txt"},
    )
    llm_node = await NodeFactory.create_async(
        session=test_session,
        workflow_id=workflow.id,
        type=NodeType.LLM,
        data={
            "label": "LLM",
            "llm_provider_id": provider.id,
            "model": "test-model",
            "system_prompt": "You are helpful.",
            "temperature": 0.1,
        },
    )
    output_node = await NodeFactory.create_async(
        session=test_session,
        workflow_id=workflow.id,
        type=NodeType.OUTPUT,
        data={"label": "Output", "format": "txt"},
    )
    await EdgeFactory.create_async(
        session=test_session,
        workflow_id=workflow.id,
        source_node_id=input_node.id,
        target_node_id=llm_node.id,
    )
    await EdgeFactory.create_async(
        session=test_session,
        workflow_id=workflow.id,
        source_node_id=llm_node.id,
        target_node_id=output_node.id,
    )
    execution = await ExecutionFactory.create_async(
        session=test_session,
        workflow_id=workflow.id,
        status=ExecutionStatus.RUNNING,
        input_data={"value": "hello"},
    )

    monkeypatch.setattr(
        "flows.prefect_execution_flow.async_session",
        lambda: _SessionContext(test_session),
    )

    with pytest.raises(RuntimeError):
        await run_workflow_execution.fn(execution.id)

    loaded = await test_session.get(Execution, execution.id)
    if loaded is None:
        pytest.fail("Execution was not found after flow completion")
        return
    execution_entity = loaded
    if execution_entity.status != ExecutionStatus.FAILED:
        pytest.fail("Execution status was not updated to failed")
    if execution_entity.error is None or "LLM exploded" not in execution_entity.error:
        pytest.fail("Execution error message did not include LLM failure reason")
    if execution_entity.finished_at is None:
        pytest.fail("Execution finished_at was not set for failed execution")
