"""Execution model factory."""

from datetime import UTC, datetime

from factory.declarations import LazyAttribute
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.execution import Execution
from db.repositories import WorkflowRepository
from enums import ExecutionSource, ExecutionStatus
from tests.factories.base import AsyncSQLAlchemyModelFactory, ModelT
from usecases.execution import ExecutionUsecase


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

    @classmethod
    async def create_async(cls, session: AsyncSession, **kwargs: object) -> ModelT:
        """Pin factory executions to a snapshot of their current workflow."""
        if "version_id" not in kwargs:
            workflow_id = kwargs.get("workflow_id")
            if not isinstance(workflow_id, int):
                message = "ExecutionFactory requires workflow_id"
                raise TypeError(message)
            workflow = await WorkflowRepository().get_by(
                session=session, id=workflow_id
            )
            if workflow is None:
                message = "ExecutionFactory workflow does not exist"
                raise ValueError(message)
            version = await ExecutionUsecase()._snapshot_workflow(  # noqa: SLF001
                session=session,
                workflow_id=workflow_id,
                owner_id=workflow.owner_id,
            )
            kwargs["version_id"] = version.id
        return await super().create_async(session=session, **kwargs)
