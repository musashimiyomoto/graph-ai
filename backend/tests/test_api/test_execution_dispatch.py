"""End-to-end async dispatch test (ARQ + real Redis).

This is the technology-validation PoC: it proves the full
enqueue -> worker -> DB round-trip works with ARQ over a real Redis, exercising
the three risky seams — Redis job serialization, the worker owning its own DB
session, and the new CREATED -> SUCCESS contract.
"""

from collections.abc import AsyncGenerator, Sequence
from typing import cast

import pytest
import pytest_asyncio
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Function, Worker
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from testcontainers.redis import RedisContainer

import worker as worker_module
from api.dependencies import queue
from db.repositories import ExecutionRepository
from enums import ExecutionStatus, NodeType
from main import app
from tests.factories import EdgeFactory, NodeFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase

pytestmark = pytest.mark.committed_db


class TestExecutionAsyncDispatch(BaseTestCase):
    """Validate the full enqueue -> worker -> DB round-trip over real Redis."""

    @pytest_asyncio.fixture
    async def redis_settings(self) -> AsyncGenerator[RedisSettings, None]:
        """Spin up a throwaway Redis and yield ARQ settings for it."""
        with RedisContainer() as container:
            yield RedisSettings(
                host=container.get_container_host_ip(),
                port=int(container.get_exposed_port(6379)),
            )

    @pytest.mark.asyncio
    async def test_enqueue_and_worker_run_end_to_end(
        self,
        test_engine: AsyncEngine,
        redis_settings: RedisSettings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST enqueues, an ARQ burst worker runs it, and the DB reaches SUCCESS."""
        # Bind the worker's DB session to the same test database.
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)

        # Point the API's ARQ pool at the throwaway Redis.
        pool = await create_pool(redis_settings)

        def override_pool() -> object:
            """Return the real ARQ pool for the API dependency."""
            return pool

        monkeypatch.setitem(app.dependency_overrides, queue.get_arq_pool, override_pool)

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
            url="/executions",
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )
        created = await self.assert_response_dict(response=response)
        if created["status"] != ExecutionStatus.CREATED:
            pytest.fail("Enqueued execution should start in CREATED state")

        # ARQ's WorkerCoroutine protocol is looser than our typed task; cast so the
        # concrete function (whose name matches the enqueued job) can be registered.
        functions = cast("Sequence[Function]", [worker_module.run_execution_task])
        arq_worker = Worker(
            functions=functions,
            redis_settings=redis_settings,
            burst=True,
            poll_delay=0.1,
            handle_signals=False,
        )
        try:
            await arq_worker.async_run()
        finally:
            await arq_worker.close()
            await pool.aclose()

        self.session.expire_all()
        finalized = await ExecutionRepository().get_by(
            session=self.session, id=created["id"]
        )
        if finalized is None:
            pytest.fail("Execution row disappeared")
        elif finalized.status != ExecutionStatus.SUCCESS:
            pytest.fail("Worker should have driven the execution to SUCCESS")
        elif finalized.output_data != {"value": "hello"}:
            pytest.fail("Worker output did not match the propagated input")
