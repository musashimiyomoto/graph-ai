"""Cron schedule receive and acknowledge adapter."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from croniter import CroniterError, croniter

from channels.base import (
    ChannelAcknowledgeContext,
    ChannelInboundEvent,
    ChannelReceiveBatch,
    ChannelReceiveContext,
)
from db.models import NodeSchedule
from db.repositories import NodeRepository, NodeScheduleRepository, WorkflowRepository
from enums import ExecutionSource, InputNodeFormat, NodeType, PortType
from schemas import NodeValuePayload, TriggerEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ScheduleCheckpoint:
    """Schedule anchor persisted after one due boundary is consumed."""

    schedule_id: int
    checked_at: datetime


class ScheduleChannelAdapter:
    """Turn due cron boundaries into normalized trigger events."""

    async def receive(
        self, context: ChannelReceiveContext
    ) -> tuple[ChannelReceiveBatch, ...]:
        """Find due schedules and build one event batch for each boundary."""
        schedule_repository = NodeScheduleRepository()
        node_repository = NodeRepository()
        workflow_repository = WorkflowRepository()
        now = datetime.now(tz=UTC)
        schedules = await schedule_repository.get_all(session=context.session)
        batches: list[ChannelReceiveBatch] = []

        for schedule in schedules:
            due_at = _due_at(schedule=schedule, now=now)
            if due_at is None:
                continue

            events: tuple[ChannelInboundEvent, ...] = ()
            node = await node_repository.get_by(
                session=context.session, id=schedule.node_id
            )
            if (
                node is not None
                and node.type is NodeType.INPUT
                and node.data.get("format") == InputNodeFormat.SCHEDULE.value
            ):
                workflow = await workflow_repository.get_by(
                    session=context.session, id=node.workflow_id
                )
                if workflow is not None:
                    value = node.data.get("scheduled_value")
                    scheduled_value = value if isinstance(value, str) else ""
                    events = (
                        ChannelInboundEvent(
                            workflow_id=node.workflow_id,
                            user_id=workflow.owner_id,
                            input_value=scheduled_value,
                            event=TriggerEvent(
                                channel=ExecutionSource.SCHEDULE,
                                external_event_id=(
                                    f"schedule:{schedule.id}:{due_at.isoformat()}"
                                ),
                                message=NodeValuePayload(
                                    kind=PortType.TEXT,
                                    value=scheduled_value,
                                ),
                                occurred_at=due_at,
                                metadata={
                                    "node_id": node.id,
                                    "schedule_id": schedule.id,
                                    "cron_expression": schedule.cron_expression,
                                },
                            ),
                        ),
                    )

            batches.append(
                ChannelReceiveBatch(
                    events=events,
                    checkpoint=_ScheduleCheckpoint(
                        schedule_id=schedule.id,
                        checked_at=now,
                    ),
                )
            )

        return tuple(batches)

    async def acknowledge(self, context: ChannelAcknowledgeContext) -> None:
        """Move a schedule anchor to the wall-clock receive time."""
        if not isinstance(context.checkpoint, _ScheduleCheckpoint):
            message = "Schedule acknowledgement requires a schedule checkpoint"
            raise TypeError(message)
        await NodeScheduleRepository().update_by(
            session=context.session,
            data={"last_fired_at": context.checkpoint.checked_at},
            id=context.checkpoint.schedule_id,
        )


def _due_at(schedule: NodeSchedule, now: datetime) -> datetime | None:
    """Return the next due cron boundary, or ``None`` when not due or invalid."""
    try:
        upcoming = croniter(schedule.cron_expression, schedule.last_fired_at).get_next(
            datetime
        )
    except CroniterError:
        logger.exception(
            "Invalid cron expression for schedule %s; skipping", schedule.id
        )
        return None
    return upcoming if upcoming <= now else None


SCHEDULE_ADAPTER = ScheduleChannelAdapter()
