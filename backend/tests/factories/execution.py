"""Execution model factory."""

from datetime import UTC, datetime

from factory.declarations import LazyAttribute

from db.models.execution import Execution
from enums import ExecutionSource, ExecutionStatus
from tests.factories.base import AsyncSQLAlchemyModelFactory


class ExecutionFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating Execution instances."""

    class Meta:
        """Factory meta configuration."""

        model = Execution

    workflow_id = None
    status = ExecutionStatus.CREATED
    source = ExecutionSource.MANUAL
    input_data = None
    trigger_event = LazyAttribute(
        lambda obj: {
            "schema_version": 1,
            "channel": obj.source.value,
            "external_event_id": None,
            "sender": None,
            "conversation": None,
            "locale": None,
            "message": {
                "kind": "text",
                "value": (obj.input_data or {}).get("value", ""),
                "artifact": None,
                "metadata": {},
            },
            "attachments": [],
            "occurred_at": datetime.now(tz=UTC).isoformat(),
            "metadata": {},
            "raw_retention": "discard",
        }
    )
