"""Delay / Wait node parsing and durable execution tests."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from constants import MAX_DELAY_SECONDS
from db.repositories import ExecutionRepository, NodeExecutionRepository
from enums import ExecutionStatus, NodeType
from exceptions import ExecutionGraphValidationError
from nodes import resolve_wait_until
from schemas import ExecutionCreate, ExecutionInputPayload
from tests.factories import EdgeFactory, NodeFactory, UserFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase
from usecases import ExecutionUsecase

pytestmark = pytest.mark.committed_db


class TestResolveWaitUntil:
    """Tests for Delay configuration parsing."""

    def test_resolves_duration_units(self) -> None:
        """Duration mode converts the selected unit into an absolute time."""
        now = datetime(2026, 7, 20, 12, tzinfo=UTC)
        resolved = resolve_wait_until(
            {"mode": "duration", "duration": 2.5, "unit": "hours"}, now
        )
        if resolved != now + timedelta(hours=2.5):
            pytest.fail("Delay duration unit was not converted correctly")

    def test_normalizes_timestamp_to_utc(self) -> None:
        """Until mode accepts an explicit offset and normalizes it to UTC."""
        now = datetime(2026, 7, 20, 12, tzinfo=UTC)
        resolved = resolve_wait_until(
            {"mode": "until", "timestamp": "2026-07-20T18:00:00+03:00"}, now
        )
        if resolved != datetime(2026, 7, 20, 15, tzinfo=UTC):
            pytest.fail("Delay timestamp was not normalized to UTC")

    @pytest.mark.parametrize(
        ("data", "message"),
        [
            (
                {"mode": "until", "timestamp": "2026-07-21T09:00:00"},
                "timezone",
            ),
            (
                {
                    "mode": "duration",
                    "duration": MAX_DELAY_SECONDS + 1,
                    "unit": "seconds",
                },
                "between",
            ),
        ],
    )
    def test_rejects_unsafe_waits(self, data: dict[str, object], message: str) -> None:
        """Naive timestamps and waits above the cap fail before checkpointing."""
        with pytest.raises(ExecutionGraphValidationError, match=message):
            resolve_wait_until(data, datetime(2026, 7, 20, 12, tzinfo=UTC))


class TestDurableDelayExecution(BaseTestCase):
    """End-to-end durable pause, resume, and cancellation behavior."""

    async def _create_execution(self) -> tuple[int, dict[str, int], int]:
        """Create an Input -> Delay -> Output execution without queueing it."""
        user = await UserFactory.create_async(session=self.session)
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user.id
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        delay_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.DELAY,
            data={
                "label": "Wait",
                "mode": "duration",
                "duration": 1,
                "unit": "hours",
            },
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        for source_id, target_id in (
            (input_node.id, delay_node.id),
            (delay_node.id, output_node.id),
        ):
            await EdgeFactory.create_async(
                session=self.session,
                workflow_id=workflow.id,
                source_node_id=source_id,
                target_node_id=target_id,
            )

        async def _noop_enqueue(_execution_id: int) -> None:
            """Keep the test in-process."""

        execution = await ExecutionUsecase().create_execution(
            session=self.session,
            user_id=user.id,
            data=ExecutionCreate(
                workflow_id=workflow.id,
                input_data=ExecutionInputPayload(value="payload"),
            ),
            enqueue=_noop_enqueue,
        )
        return (
            execution.id,
            {"input": input_node.id, "delay": delay_node.id, "output": output_node.id},
            user.id,
        )

    @pytest.mark.asyncio
    async def test_resume_reuses_checkpoint_without_repeating_nodes(
        self, test_engine: AsyncEngine
    ) -> None:
        """A due continuation passes input through and records every node once."""
        execution_id, node_ids, _ = await self._create_execution()
        factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        usecase = ExecutionUsecase()

        waiting = await usecase.run_execution(
            session=self.session,
            execution_id=execution_id,
            session_factory=factory,
        )
        if waiting.status is not ExecutionStatus.WAITING_DELAY:
            pytest.fail("Execution should release the worker at Delay")
        if waiting.wait_until is None or waiting.queue_job_id is None:
            pytest.fail("Delay checkpoint should expose scheduling metadata")

        node_repository = NodeExecutionRepository()
        waiting_rows = await node_repository.get_all(
            session=self.session,
            execution_id=execution_id,
            status=ExecutionStatus.WAITING_DELAY,
        )
        if len(waiting_rows) != 1 or waiting_rows[0].node_id != node_ids["delay"]:
            pytest.fail("Delay node should have one durable waiting row")

        past = datetime.now(tz=UTC) - timedelta(seconds=1)
        await node_repository.update_by(
            session=self.session, id=waiting_rows[0].id, data={"wait_until": past}
        )
        await ExecutionRepository().update_by(
            session=self.session, id=execution_id, data={"wait_until": past}
        )
        await self.session.commit()

        finalized = await usecase.run_execution(
            session=self.session,
            execution_id=execution_id,
            session_factory=factory,
        )
        if finalized.status is not ExecutionStatus.SUCCESS:
            pytest.fail("Due Delay continuation should finish successfully")
        if finalized.output_data != {"value": "payload"}:
            pytest.fail("Delay should pass upstream text through unchanged")

        rows = await node_repository.get_all(
            session=self.session, execution_id=execution_id
        )
        counts = {
            node_id: sum(row.node_id == node_id for row in rows)
            for node_id in node_ids.values()
        }
        if counts != dict.fromkeys(node_ids.values(), 1):
            pytest.fail("Resume should not duplicate completed node executions")

    @pytest.mark.asyncio
    async def test_waiting_delay_can_be_cancelled(
        self, test_engine: AsyncEngine
    ) -> None:
        """Cancellation finalizes both the run and its waiting node row."""
        execution_id, _, user_id = await self._create_execution()
        factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        usecase = ExecutionUsecase()
        await usecase.run_execution(
            session=self.session,
            execution_id=execution_id,
            session_factory=factory,
        )

        cancelled = await usecase.cancel_execution(
            session=self.session,
            execution_id=execution_id,
            user_id=user_id,
        )
        if cancelled.status is not ExecutionStatus.CANCELLED:
            pytest.fail("Waiting Delay execution should be cancellable")
        waiting_rows = await NodeExecutionRepository().get_all(
            session=self.session,
            execution_id=execution_id,
            status=ExecutionStatus.CANCELLED,
        )
        if not any(row.node_type is NodeType.DELAY for row in waiting_rows):
            pytest.fail("Delay checkpoint row should be finalized as cancelled")
