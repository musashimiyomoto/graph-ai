"""Worker Telegram polling and reply tests."""

from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

import channels.email as email_channel
import channels.telegram as telegram_channel
import channels.webhook as webhook_channel
import worker as worker_module
from db.repositories import (
    EmailAccountRepository,
    ExecutionRepository,
    NodeScheduleRepository,
    TelegramBotRepository,
)
from enums import ExecutionSource, ExecutionStatus, NodeType, PortType
from integrations.email import EmailConnectionConfig, InboundEmail
from schemas import (
    ExecutionCreate,
    ExecutionInputPayload,
    NodeValuePayload,
    TriggerActor,
    TriggerConversation,
    TriggerEvent,
)
from tests.factories import (
    EdgeFactory,
    EmailAccountFactory,
    NodeFactory,
    NodeScheduleFactory,
    TelegramBotFactory,
    UserFactory,
    WorkflowFactory,
)
from tests.test_api.base import BaseTestCase
from usecases import ExecutionTrigger, ExecutionUsecase

pytestmark = pytest.mark.committed_db

_FAKE_CHAT_ID = 999
_FAKE_UPDATE_ID = 501
_PINNED_CHAT_ID = 555
_FAKE_EMAIL_UID = 701


def _telegram_trigger() -> ExecutionTrigger:
    """Build a canonical Telegram trigger for delivery tests."""
    return ExecutionTrigger(
        source=ExecutionSource.TELEGRAM,
        event=TriggerEvent(
            channel=ExecutionSource.TELEGRAM,
            external_event_id="test-telegram-reply",
            conversation=TriggerConversation(id=str(_FAKE_CHAT_ID)),
            message=NodeValuePayload(kind=PortType.TEXT, value="hello"),
            occurred_at=datetime.now(tz=UTC),
        ),
    )


class _FakeRedis:
    """Stand-in ARQ redis connection recording enqueue calls."""

    def __init__(self) -> None:
        """Initialize the call log."""
        self.enqueued: list[int] = []
        self.enqueue_options: list[dict[str, object]] = []

    async def enqueue_job(
        self, _name: str, execution_id: int, **kwargs: object
    ) -> None:
        """Record the enqueued execution ID."""
        self.enqueued.append(execution_id)
        self.enqueue_options.append(dict(kwargs))


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
                "message_id": 88,
                "date": 1_721_600_000,
                "text": "hello from telegram",
                "chat": {"id": _FAKE_CHAT_ID},
                "from": {
                    "id": 123,
                    "first_name": "Ada",
                    "username": "ada",
                    "language_code": "en",
                },
            },
        }
    ]


async def _fake_fetch_messages(
    config: EmailConnectionConfig, last_uid: int
) -> list[InboundEmail]:
    """Return one normalized incoming email."""
    del config, last_uid
    return [
        InboundEmail(
            uid=_FAKE_EMAIL_UID,
            sender="customer@example.com",
            subject="Need help",
            body="My order is late",
            message_id="<message-701@example.com>",
            thread_id="<order-7@example.com>",
            sent_at=datetime(2026, 7, 21, 12, tzinfo=UTC),
            locale="en",
        )
    ]


class _FakeSendEmail:
    """Record SMTP delivery calls."""

    calls: ClassVar[list[tuple[str, str, str]]] = []

    async def __call__(
        self,
        config: EmailConnectionConfig,
        recipient: str,
        subject: str,
        text: str,
    ) -> None:
        """Record a message instead of connecting to SMTP."""
        del config
        _FakeSendEmail.calls.append((recipient, subject, text))


class _FakeSendWebhook:
    """Record outbound webhook delivery calls."""

    calls: ClassVar[list[tuple[str, dict[str, Any]]]] = []

    async def __call__(self, url: str, payload: dict[str, Any]) -> None:
        """Record the callback URL and JSON body."""
        _FakeSendWebhook.calls.append((url, payload))


class TestPollTelegramUpdates(BaseTestCase):
    """Tests for the registered Telegram receiver."""

    @pytest.mark.asyncio
    async def test_creates_execution_and_advances_offset(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A new Telegram message enqueues an execution and advances the offset."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)
        monkeypatch.setattr(telegram_channel, "get_updates", _fake_get_updates)

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

        await worker_module.poll_registered_channel(
            {"redis": _FakeRedis()}, ExecutionSource.TELEGRAM
        )

        self.session.expire_all()
        executions = await ExecutionRepository().get_all(
            session=self.session, workflow_id=workflow_id
        )
        if len(executions) != 1:
            pytest.fail(f"Expected exactly one execution, got {len(executions)}")
        execution = executions[0]
        if execution.input_data != {"value": "hello from telegram"}:
            pytest.fail("Execution input did not carry the Telegram message text")
        event = execution.trigger_event
        if event["external_event_id"] != f"bot:{bot_id}:update:{_FAKE_UPDATE_ID}":
            pytest.fail("Telegram update ID was not persisted for idempotency")
        if event["sender"]["address"] != "@ada":
            pytest.fail("Telegram sender metadata was not normalized")
        if event["conversation"]["id"] != str(_FAKE_CHAT_ID):
            pytest.fail("Telegram chat was not normalized as the conversation")

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

        monkeypatch.setattr(telegram_channel, "get_updates", _fail_if_called)

        user = await UserFactory.create_async(session=self.session)
        await TelegramBotFactory.create_async(session=self.session, user_id=user.id)

        await worker_module.poll_registered_channel(
            {"redis": _FakeRedis()}, ExecutionSource.TELEGRAM
        )


class TestDelayScheduling(BaseTestCase):
    """Tests for releasing a worker at a durable Delay checkpoint."""

    @pytest.mark.asyncio
    async def test_enqueues_continuation_for_wake_up_time(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The worker schedules a fresh deferred job instead of sleeping."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)
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
                "duration": 5,
                "unit": "minutes",
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
            """Run the initial job inline."""

        execution = await ExecutionUsecase().create_execution(
            session=self.session,
            user_id=user.id,
            data=ExecutionCreate(
                workflow_id=workflow.id,
                input_data=ExecutionInputPayload(value="payload"),
            ),
            enqueue=_noop_enqueue,
        )
        redis = _FakeRedis()

        await worker_module.run_execution_task({"redis": redis}, execution.id)

        if redis.enqueued != [execution.id]:
            pytest.fail("Delay should enqueue exactly one continuation")
        options = redis.enqueue_options[0]
        if ":delay:" not in str(options.get("_job_id")):
            pytest.fail("Delay continuation should use a fresh job ID")
        if not isinstance(options.get("_defer_until"), datetime):
            pytest.fail("Delay continuation should be deferred until its checkpoint")


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
        monkeypatch.setattr(telegram_channel, "send_message", fake_send_message)

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
            trigger=_telegram_trigger(),
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
        monkeypatch.setattr(telegram_channel, "send_message", fake_send_message)

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
        monkeypatch.setattr(telegram_channel, "send_message", fake_send_message)

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
            trigger=_telegram_trigger(),
        )

        await worker_module.run_execution_task({"redis": _FakeRedis()}, execution.id)

        if fake_send_message.calls:
            pytest.fail("No Telegram reply should be sent without format=telegram")


class TestPollEmailUpdates(BaseTestCase):
    """Tests for the registered email receiver."""

    async def test_creates_email_execution_and_advances_uid(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A new email is persisted with reply metadata and advances the UID."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)
        monkeypatch.setattr(email_channel, "fetch_messages", _fake_fetch_messages)

        user = await UserFactory.create_async(session=self.session)
        account = await EmailAccountFactory.create_async(
            session=self.session, user_id=user.id
        )
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user.id
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={
                "label": "Input",
                "format": "email",
                "email_account_id": account.id,
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
        workflow_id = workflow.id
        account_id = account.id

        await worker_module.poll_registered_channel(
            {"redis": _FakeRedis()}, ExecutionSource.EMAIL
        )

        self.session.expire_all()
        executions = await ExecutionRepository().get_all(
            session=self.session, workflow_id=workflow_id
        )
        if len(executions) != 1:
            pytest.fail(f"Expected one email execution, got {len(executions)}")
        execution = executions[0]
        if execution.source is not ExecutionSource.EMAIL:
            pytest.fail("Execution was not tagged with the email source")
        if execution.input_data != {"value": "Subject: Need help\n\nMy order is late"}:
            pytest.fail("Email subject and body did not reach the workflow input")
        event = execution.trigger_event
        if event["external_event_id"] != f"account:{account_id}:uid:{_FAKE_EMAIL_UID}":
            pytest.fail("Email UID was not persisted for idempotency")
        if event["conversation"]["id"] != "<order-7@example.com>":
            pytest.fail("Email thread was not normalized")
        if event["sender"]["address"] != "customer@example.com":
            pytest.fail("Email sender was not normalized")
        if event["metadata"]["subject"] != "Need help":
            pytest.fail("Email subject was not normalized")
        refreshed = await EmailAccountRepository().get_by(
            session=self.session, id=account_id
        )
        if refreshed is None or refreshed.last_uid != _FAKE_EMAIL_UID:
            pytest.fail("Email UID offset was not advanced")


class TestEmailReply(BaseTestCase):
    """Tests for SMTP delivery after an execution finishes."""

    async def test_replies_to_triggering_sender(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Email Output uses the trigger sender and derives a reply subject."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)
        fake_send_email = _FakeSendEmail()
        _FakeSendEmail.calls = []
        monkeypatch.setattr(email_channel, "send_email", fake_send_email)

        user = await UserFactory.create_async(session=self.session)
        account = await EmailAccountFactory.create_async(
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
                "format": "email",
                "email_account_id": account.id,
            },
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=output_node.id,
        )

        async def _noop_enqueue(_execution_id: int) -> None:
            """Skip ARQ enqueue; execute the job inline."""

        execution = await ExecutionUsecase().create_execution(
            session=self.session,
            user_id=user.id,
            data=ExecutionCreate(
                workflow_id=workflow.id,
                input_data=ExecutionInputPayload(value="resolved"),
            ),
            enqueue=_noop_enqueue,
            trigger=ExecutionTrigger(
                source=ExecutionSource.EMAIL,
                event=TriggerEvent(
                    channel=ExecutionSource.EMAIL,
                    external_event_id="test-email-reply",
                    sender=TriggerActor(
                        id="customer@example.com",
                        address="customer@example.com",
                    ),
                    message=NodeValuePayload(
                        kind=PortType.TEXT,
                        value="resolved",
                    ),
                    occurred_at=datetime.now(tz=UTC),
                    metadata={"subject": "Need help"},
                ),
            ),
        )

        await worker_module.run_execution_task({"redis": _FakeRedis()}, execution.id)

        if _FakeSendEmail.calls != [
            ("customer@example.com", "Re: Need help", "resolved")
        ]:
            pytest.fail(f"Unexpected email delivery: {_FakeSendEmail.calls}")


class TestWebhookDelivery(BaseTestCase):
    """Tests for callback delivery after an execution finishes."""

    async def test_posts_finished_execution(
        self, test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Webhook Output receives the final status and output payload."""
        worker_sessionmaker = async_sessionmaker(
            bind=test_engine, expire_on_commit=False
        )
        monkeypatch.setattr(worker_module, "async_session", worker_sessionmaker)
        fake_send_webhook = _FakeSendWebhook()
        _FakeSendWebhook.calls = []
        monkeypatch.setattr(webhook_channel, "send_webhook", fake_send_webhook)

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
            data={
                "label": "Output",
                "format": "webhook",
                "webhook_url": "https://hooks.example.com/result",
            },
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=output_node.id,
        )

        async def _noop_enqueue(_execution_id: int) -> None:
            """Skip ARQ enqueue; execute the job inline."""

        execution = await ExecutionUsecase().create_execution(
            session=self.session,
            user_id=user.id,
            data=ExecutionCreate(
                workflow_id=workflow.id,
                input_data=ExecutionInputPayload(value="callback result"),
            ),
            enqueue=_noop_enqueue,
        )

        await worker_module.run_execution_task({"redis": _FakeRedis()}, execution.id)

        expected_payload = {
            "execution_id": execution.id,
            "workflow_id": workflow.id,
            "status": ExecutionStatus.SUCCESS.value,
            "output": {"value": "callback result"},
            "error": None,
        }
        if _FakeSendWebhook.calls != [
            ("https://hooks.example.com/result", expected_payload)
        ]:
            pytest.fail(f"Unexpected webhook delivery: {_FakeSendWebhook.calls}")


class TestPollScheduledTriggers(BaseTestCase):
    """Tests for the registered schedule receiver."""

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

        await worker_module.poll_registered_channel(
            {"redis": _FakeRedis()}, ExecutionSource.SCHEDULE
        )

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

        await worker_module.poll_registered_channel(
            {"redis": _FakeRedis()}, ExecutionSource.SCHEDULE
        )

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

        await worker_module.poll_registered_channel(
            {"redis": _FakeRedis()}, ExecutionSource.SCHEDULE
        )

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
        await worker_module.poll_registered_channel(
            {"redis": _FakeRedis()}, ExecutionSource.SCHEDULE
        )

        self.session.expire_all()
        executions = await ExecutionRepository().get_all(session=self.session)
        if executions:
            pytest.fail("An invalid cron expression should never create an execution")
