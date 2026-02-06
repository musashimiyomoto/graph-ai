"""Edge model factory."""

from models.edge import Edge
from tests.factories.base import AsyncSQLAlchemyModelFactory


class EdgeFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating Edge instances."""

    class Meta:
        """Factory meta configuration."""

        model = Edge

    workflow_id = None
    source_node_id = None
    target_node_id = None
