"""Provider-neutral channel adapter contracts and runtime values."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from enums import ExecutionSource, ExecutionStatus, InputNodeFormat, OutputNodeFormat
from schemas import NodeFieldSpec, TriggerEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from db.models import Execution, Node


@dataclass(frozen=True)
class ChannelInboundEvent:
    """One normalized provider event ready to create an execution."""

    workflow_id: int
    user_id: int
    input_value: str
    event: TriggerEvent


@dataclass(frozen=True)
class ChannelReceiveBatch:
    """Events fetched together and the provider cursor to acknowledge."""

    events: tuple[ChannelInboundEvent, ...]
    checkpoint: object | None = None


@dataclass(frozen=True)
class ChannelReceiveContext:
    """Dependencies and optional push payload supplied to a receiver."""

    session: "AsyncSession"
    payload: object | None = None


@dataclass(frozen=True)
class ChannelAcknowledgeContext:
    """Provider cursor acknowledgement context."""

    session: "AsyncSession"
    checkpoint: object


@dataclass(frozen=True)
class ChannelDeliveryContext:
    """Finished execution and configured Output node supplied to a deliverer."""

    session: "AsyncSession"
    execution: "Execution"
    output_node: "Node"


class ChannelReceiver(Protocol):
    """Adapter contract for normalizing one polling or push receive cycle."""

    async def receive(
        self, context: ChannelReceiveContext
    ) -> tuple[ChannelReceiveBatch, ...]:
        """Return normalized inbound event batches."""


class ChannelAcknowledger(Protocol):
    """Adapter contract for committing a provider cursor after receive."""

    async def acknowledge(self, context: ChannelAcknowledgeContext) -> None:
        """Persist one successfully consumed provider checkpoint."""


class ChannelDeliverer(Protocol):
    """Adapter contract for delivering one finished execution."""

    async def deliver(self, context: ChannelDeliveryContext) -> None:
        """Deliver the result through the configured channel."""


@dataclass(frozen=True)
class ChannelSettingsSpec:
    """Frontend settings section backed by a channel account resource."""

    key: str
    label: str
    component_key: str


@dataclass(frozen=True)
class ChannelDefinition:
    """Declarative metadata and adapters for one registered channel."""

    source: ExecutionSource
    label: str
    icon_key: str
    input_format: InputNodeFormat | None
    output_format: OutputNodeFormat | None
    activity: bool
    input_fields: tuple[NodeFieldSpec, ...] = ()
    output_fields: tuple[NodeFieldSpec, ...] = ()
    settings: ChannelSettingsSpec | None = None
    receiver: ChannelReceiver | None = None
    acknowledger: ChannelAcknowledger | None = None
    deliverer: ChannelDeliverer | None = None
    poll_seconds: frozenset[int] | None = None


def delivery_text(execution: "Execution") -> str | None:
    """Resolve the text delivered for a terminal execution."""
    if execution.status is ExecutionStatus.SUCCESS:
        output = execution.output_data or {}
        value = output.get("value", "") if isinstance(output, dict) else ""
        return str(value) or "(empty output)"
    if execution.status is ExecutionStatus.FAILED:
        return f"Execution failed: {execution.error or 'unknown error'}"
    return None
