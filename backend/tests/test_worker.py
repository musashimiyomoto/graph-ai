"""Worker Telegram polling and reply tests."""

from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

import worker as worker_module
from db.repositories import (
    ExecutionRepository,
    NodeScheduleRepository,
    TelegramBotRepository,
)
from enums import ExecutionSource, ExecutionStatus, NodeType
from schemas import ExecutionCreate, ExecutionInputPayload
from tests.factories import (
    EdgeFactory,
    NodeFactory,
    NodeScheduleFactory,
    TelegramBotFactory,
    UserFactory,
    WorkflowFactory,
)
from tests.test_api.base import BaseTestCase
from usecases import ExecutionTrigger, ExecutionUsecase

_FAKE_CHAT_ID = 999
_FAKE_UPDATE_ID = 501
_PINNED_CHAT_ID = 555


class _FakeRedis:
    """Stand-in ARQ redis connection recording enqueue calls."""

    def __init__(self) -> None:
        """Initialize the call log."""
        self.enqueued: list[int] = []

    async def enqueue_job(
        self, _name: str, execution_id: int, **kwargs: object
    ) -> None:
        """Record the enqueued execution ID."""
        del kwargs
        self.enqueued.append(execution_id)


class _FakeSendMessage:
    """Stand-in for ``integrations.telegram.send_message`` recording calls."""

    calls: ClassVar[list[tuple[str, int, str]]] = []

    async def __call__(self, bot_token: str, chat_id: int, text: str) -> None:
        """Record the call instead of hitting Telegram."""
        _FakeSendMessage.calls.append((bot_token, chat_id, text))


async def _fake_get_updates(
    bot_token: str, offset: int, **kwargs: object
) -> list[dict[str, Any]]:
    """Return one fixed Telegram update regardless of arguments."""
    del bot_token, offset, kwargs
    return [
        {
            "update_id": _FAKE_UPDATE_ID,
            "message": {
                "text": "hello from telegram",
                "chat": {"id": _FAKE_CHAT_ID},
            },
        }
    ]


class TestPollTelegramUpdates(BaseTestCase):
    """Tests for ``worker.poll_telegram_updates``."""

    @pytest.mark.asyncio
    async def test_creates_execution_and_advances_offset(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A new Telegram message enqueues an execution and advances the offset."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)
        monkeypatch.setattr(worker_module, "get_updates", _fake_get_updates)

        user = await UserFactory.create_async(session=self.session)
        bot = await TelegramBotFactory.create_async(
            session=self.session, user_id=user.id
        )
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user.id
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "telegram", "telegram_bot_id": bot.id},
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

        workflow_id = workflow.id
        bot_id = bot.id

        await worker_module.poll_telegram_updates({"redis": _FakeRedis()})

        self.session.expire_all()
        executions = await ExecutionRepository().get_all(
            session=self.session, workflow_id=workflow_id
        )
        if len(executions) != 1:
            pytest.fail(f"Expected exactly one execution, got {len(executions)}")
        execution = executions[0]
        if execution.telegram_chat_id != _FAKE_CHAT_ID:
            pytest.fail("Execution was not tagged with the triggering chat ID")
        if execution.input_data != {"value": "hello from telegram"}:
            pytest.fail("Execution input did not carry the Telegram message text")

        refreshed_bot = await TelegramBotRepository().get_by(
            session=self.session, id=bot_id
        )
        if refreshed_bot is None or refreshed_bot.last_update_id != _FAKE_UPDATE_ID:
            pytest.fail("Bot poll offset was not advanced")

    @pytest.mark.asyncio
    async def test_ignores_nodes_not_wired_to_this_bot(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bot with no referencing Input node is never polled."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)

        async def _fail_if_called(*args: object, **kwargs: object) -> list[Any]:
            """Fail the test if the poller reaches out to Telegram at all."""
            del args, kwargs
            pytest.fail("get_updates should not be called for an unreferenced bot")

        monkeypatch.setattr(worker_module, "get_updates", _fail_if_called)

        user = await UserFactory.create_async(session=self.session)
        await TelegramBotFactory.create_async(session=self.session, user_id=user.id)

        await worker_module.poll_telegram_updates({"redis": _FakeRedis()})


class TestTelegramReply(BaseTestCase):
    """Tests for the worker replying to Telegram after an execution finishes."""

    @pytest.mark.asyncio
    async def test_sends_reply_when_output_configured_for_telegram(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A Telegram-triggered execution replies through the Output node's bot."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)
        fake_send_message = _FakeSendMessage()
        _FakeSendMessage.calls = []
        monkeypatch.setattr(worker_module, "send_message", fake_send_message)

        user = await UserFactory.create_async(session=self.session)
        bot = await TelegramBotFactory.create_async(
            session=self.session, user_id=user.id
        )
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user.id
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
            data={"label": "Output", "format": "telegram", "telegram_bot_id": bot.id},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=output_node.id,
        )

        async def _noop_enqueue(_execution_id: int) -> None:
            """Skip the real ARQ enqueue; the test runs the job inline."""

        execution = await ExecutionUsecase().create_execution(
            session=self.session,
            user_id=user.id,
            data=ExecutionCreate(
                workflow_id=workflow.id,
                input_data=ExecutionInputPayload(value="hello"),
            ),
            enqueue=_noop_enqueue,
            trigger=ExecutionTrigger(telegram_chat_id=_FAKE_CHAT_ID),
        )

        await worker_module.run_execution_task({"redis": _FakeRedis()}, execution.id)

        self.session.expire_all()
        finalized = await ExecutionRepository().get_by(
            session=self.session, id=execution.id
        )
        if finalized is None or finalized.status != ExecutionStatus.SUCCESS:
            pytest.fail("Execution should have completed successfully")

        if len(fake_send_message.calls) != 1:
            pytest.fail(
                f"Expected exactly one Telegram reply, got "
                f"{len(fake_send_message.calls)}"
            )
        _, chat_id, text = fake_send_message.calls[0]
        if chat_id != _FAKE_CHAT_ID:
            pytest.fail("Reply was sent to the wrong chat")
        if text != "hello":
            pytest.fail("Reply did not carry the execution output")

    @pytest.mark.asyncio
    async def test_sends_reply_to_pinned_chat_for_manual_run(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A manual run still replies when the Output node pins a chat ID."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)
        fake_send_message = _FakeSendMessage()
        _FakeSendMessage.calls = []
        monkeypatch.setattr(worker_module, "send_message", fake_send_message)

        user = await UserFactory.create_async(session=self.session)
        bot = await TelegramBotFactory.create_async(
            session=self.session, user_id=user.id
        )
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user.id
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
            data={
                "label": "Output",
                "format": "telegram",
                "telegram_bot_id": bot.id,
                "telegram_chat_id": _PINNED_CHAT_ID,
            },
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=output_node.id,
        )

        async def _noop_enqueue(_execution_id: int) -> None:
            """Skip the real ARQ enqueue; the test runs the job inline."""

        # No telegram_chat_id passed: this mirrors a manual run through the
        # public API, which never sets it.
        execution = await ExecutionUsecase().create_execution(
            session=self.session,
            user_id=user.id,
            data=ExecutionCreate(
                workflow_id=workflow.id,
                input_data=ExecutionInputPayload(value="hello"),
            ),
            enqueue=_noop_enqueue,
        )

        await worker_module.run_execution_task({"redis": _FakeRedis()}, execution.id)

        if len(fake_send_message.calls) != 1:
            pytest.fail(
                f"Expected exactly one Telegram reply, got "
                f"{len(fake_send_message.calls)}"
            )
        _, chat_id, text = fake_send_message.calls[0]
        if chat_id != _PINNED_CHAT_ID:
            pytest.fail("Reply was not sent to the pinned chat")
        if text != "hello":
            pytest.fail("Reply did not carry the execution output")

    @pytest.mark.asyncio
    async def test_no_reply_when_output_not_configured_for_telegram(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No reply is sent when the Output node's format isn't Telegram."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)
        fake_send_message = _FakeSendMessage()
        _FakeSendMessage.calls = []
        monkeypatch.setattr(worker_module, "send_message", fake_send_message)

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

        async def _noop_enqueue(_execution_id: int) -> None:
            """Skip the real ARQ enqueue; the test runs the job inline."""

        execution = await ExecutionUsecase().create_execution(
            session=self.session,
            user_id=user.id,
            data=ExecutionCreate(
                workflow_id=workflow.id,
                input_data=ExecutionInputPayload(value="hello"),
            ),
            enqueue=_noop_enqueue,
            trigger=ExecutionTrigger(telegram_chat_id=_FAKE_CHAT_ID),
        )

        await worker_module.run_execution_task({"redis": _FakeRedis()}, execution.id)

        if fake_send_message.calls:
            pytest.fail("No Telegram reply should be sent without format=telegram")


class TestPollScheduledTriggers(BaseTestCase):
    """Tests for ``worker.poll_scheduled_triggers``."""

    async def _create_scheduled_workflow(
        self,
        user_id: int,
        cron_expression: str,
        last_fired_at: datetime,
        scheduled_value: str = "",
    ) -> int:
        """Create a minimal Input(schedule)->Output workflow with a schedule row.

        Returns:
            The created Input node's ID.

        """
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user_id
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={
                "label": "Input",
                "format": "schedule",
                "cron_expression": cron_expression,
                "scheduled_value": scheduled_value,
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
        await NodeScheduleFactory.create_async(
            session=self.session,
            node_id=input_node.id,
            cron_expression=cron_expression,
            last_fired_at=last_fired_at,
        )
        return input_node.id

    @pytest.mark.asyncio
    async def test_fires_a_due_schedule_and_advances_last_fired_at(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A schedule whose next boundary has passed creates an execution."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)

        user = await UserFactory.create_async(session=self.session)
        # Every-minute cron, anchored 2 minutes ago: certainly due.
        node_id = await self._create_scheduled_workflow(
            user_id=user.id,
            cron_expression="* * * * *",
            last_fired_at=datetime.now(tz=UTC) - timedelta(minutes=2),
        )

        await worker_module.poll_scheduled_triggers({"redis": _FakeRedis()})

        self.session.expire_all()
        executions = await ExecutionRepository().get_all(session=self.session)
        if len(executions) != 1:
            pytest.fail(f"Expected exactly one execution, got {len(executions)}")
        execution = executions[0]
        if execution.source != ExecutionSource.SCHEDULE:
            pytest.fail("Execution was not tagged with the SCHEDULE source")
        if execution.input_data != {"value": ""}:
            pytest.fail("Scheduled execution should carry an empty input value")

        schedule = await NodeScheduleRepository().get_by(
            session=self.session, node_id=node_id
        )
        if schedule is None or schedule.last_fired_at <= datetime.now(
            tz=UTC
        ) - timedelta(minutes=1):
            pytest.fail("last_fired_at should have advanced to roughly now")

    @pytest.mark.asyncio
    async def test_fires_with_the_node_configured_scheduled_value(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A due schedule's execution carries the Input node's fixed value."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)

        user = await UserFactory.create_async(session=self.session)
        await self._create_scheduled_workflow(
            user_id=user.id,
            cron_expression="* * * * *",
            last_fired_at=datetime.now(tz=UTC) - timedelta(minutes=2),
            scheduled_value="latest AI news",
        )

        await worker_module.poll_scheduled_triggers({"redis": _FakeRedis()})

        self.session.expire_all()
        executions = await ExecutionRepository().get_all(session=self.session)
        if len(executions) != 1:
            pytest.fail(f"Expected exactly one execution, got {len(executions)}")
        if executions[0].input_data != {"value": "latest AI news"}:
            pytest.fail("Execution should carry the node's configured scheduled_value")

    @pytest.mark.asyncio
    async def test_ignores_a_schedule_not_yet_due(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A schedule anchored moments ago on an hourly cron is left alone."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)

        user = await UserFactory.create_async(session=self.session)
        anchor = datetime.now(tz=UTC)
        node_id = await self._create_scheduled_workflow(
            user_id=user.id,
            cron_expression="0 * * * *",
            last_fired_at=anchor,
        )

        await worker_module.poll_scheduled_triggers({"redis": _FakeRedis()})

        self.session.expire_all()
        executions = await ExecutionRepository().get_all(session=self.session)
        if executions:
            pytest.fail("A not-yet-due schedule should not create an execution")

        schedule = await NodeScheduleRepository().get_by(
            session=self.session, node_id=node_id
        )
        if schedule is None or schedule.last_fired_at != anchor:
            pytest.fail("A not-yet-due schedule's anchor should not move")

    @pytest.mark.asyncio
    async def test_invalid_cron_expression_is_skipped_not_raised(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A malformed cron expression is logged and skipped, not fatal."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)

        user = await UserFactory.create_async(session=self.session)
        await self._create_scheduled_workflow(
            user_id=user.id,
            cron_expression="not a cron",
            last_fired_at=datetime.now(tz=UTC) - timedelta(minutes=2),
        )

        # Must not raise.
        await worker_module.poll_scheduled_triggers({"redis": _FakeRedis()})

        self.session.expire_all()
        executions = await ExecutionRepository().get_all(session=self.session)
        if executions:
            pytest.fail("An invalid cron expression should never create an execution")
