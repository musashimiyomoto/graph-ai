"""Generic channel receive/acknowledge and delivery orchestration."""

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from channels.base import (
    ChannelAcknowledgeContext,
    ChannelDeliveryContext,
    ChannelReceiveContext,
)
from channels.registry import get_channel_definition, get_output_channel
from db.repositories import ExecutionRepository, NodeRepository
from enums import ExecutionSource, NodeType
from exceptions import BaseError
from schemas import ExecutionCreate, ExecutionInputPayload, ExecutionResponse

logger = logging.getLogger(__name__)


async def receive_channel(
    *,
    source: ExecutionSource,
    session: AsyncSession,
    enqueue: Callable[[int], Awaitable[None]],
    payload: object | None = None,
    continue_on_error: bool = False,
) -> list[ExecutionResponse]:
    """Receive, persist, enqueue, and acknowledge one registered channel cycle."""
    # Imported at the orchestration boundary to keep the channel package usable
    # while ``usecases.__init__`` eagerly exports the public channel use cases.
    from usecases.execution import (  # noqa: PLC0415
        ExecutionTrigger,
        ExecutionUsecase,
    )

    definition = get_channel_definition(source)
    if definition.receiver is None:
        message = f"Channel '{source.value}' does not support receive"
        raise RuntimeError(message)

    batches = await definition.receiver.receive(
        ChannelReceiveContext(session=session, payload=payload)
    )
    responses: list[ExecutionResponse] = []
    execution_usecase = ExecutionUsecase()
    for batch in batches:
        for inbound in batch.events:
            try:
                response = await execution_usecase.create_execution(
                    session=session,
                    user_id=inbound.user_id,
                    data=ExecutionCreate(
                        workflow_id=inbound.workflow_id,
                        input_data=ExecutionInputPayload(value=inbound.input_value),
                    ),
                    enqueue=enqueue,
                    trigger=ExecutionTrigger(source=source, event=inbound.event),
                )
            except BaseError:
                if not continue_on_error:
                    raise
                logger.exception(
                    "Failed to create %s execution for workflow %s",
                    source.value,
                    inbound.workflow_id,
                )
            else:
                responses.append(response)

        if batch.checkpoint is not None:
            if definition.acknowledger is None:
                message = (
                    f"Channel '{source.value}' returned a checkpoint without an "
                    "acknowledge adapter"
                )
                raise RuntimeError(message)
            await definition.acknowledger.acknowledge(
                ChannelAcknowledgeContext(
                    session=session,
                    checkpoint=batch.checkpoint,
                )
            )
            await session.commit()

    return responses


async def deliver_execution(*, session: AsyncSession, execution_id: int) -> None:
    """Dispatch one finished execution through its registered Output channel."""
    execution = await ExecutionRepository().get_by(session=session, id=execution_id)
    if execution is None:
        return
    output_node = await NodeRepository().get_by(
        session=session,
        workflow_id=execution.workflow_id,
        type=NodeType.OUTPUT,
        parent_node_id=None,
    )
    if output_node is None:
        return
    definition = get_output_channel(output_node.data.get("format"))
    if definition is None or definition.deliverer is None:
        return
    try:
        await definition.deliverer.deliver(
            ChannelDeliveryContext(
                session=session,
                execution=execution,
                output_node=output_node,
            )
        )
    except BaseError:
        logger.exception(
            "Failed to deliver %s result for execution %s",
            definition.source.value,
            execution_id,
        )
