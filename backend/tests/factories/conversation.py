"""Conversation model factory."""

from datetime import UTC, datetime
from uuid import uuid4

from factory.declarations import LazyFunction

from db.models import Conversation
from enums import ExecutionSource
from tests.factories.base import AsyncSQLAlchemyModelFactory


class ConversationFactory(AsyncSQLAlchemyModelFactory):
    """Factory for durable workflow conversation records."""

    class Meta:
        """Factory meta configuration."""

        model = Conversation

    owner_id = None
    workflow_id = None
    channel = ExecutionSource.WEB_CHAT
    external_thread = LazyFunction(lambda: uuid4().hex)
    external_conversation_id = LazyFunction(lambda: f"visitor-{uuid4().hex}")
    public_id = LazyFunction(lambda: uuid4().hex)
    last_event_at = LazyFunction(lambda: datetime.now(tz=UTC))
