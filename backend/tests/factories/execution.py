"""Execution model factory."""

from db.models.execution import Execution
from enums import ExecutionStatus
from tests.factories.base import AsyncSQLAlchemyModelFactory


class ExecutionFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating Execution instances."""

    class Meta:
        """Factory meta configuration."""

        model = Execution

    workflow_id = None
    status = ExecutionStatus.CREATED
    input_data = None
