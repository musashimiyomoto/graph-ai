"""Node execution model factory."""

from db.models.node_execution import NodeExecution
from enums import ExecutionStatus
from tests.factories.base import AsyncSQLAlchemyModelFactory


class NodeExecutionFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating NodeExecution instances."""

    class Meta:
        """Factory meta configuration."""

        model = NodeExecution

    execution_id = None
    node_id = None
    status = ExecutionStatus.SUCCESS
    output_values = None
    error = None
