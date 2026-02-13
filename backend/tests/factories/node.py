"""Node model factory."""

from factory.declarations import LazyAttribute

from db.models.node import Node
from enums import NodeType
from enums.node import InputNodeFormat
from tests.factories.base import AsyncSQLAlchemyModelFactory, fake


class NodeFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating Node instances."""

    class Meta:
        """Factory meta configuration."""

        model = Node

    workflow_id = None
    type = NodeType.INPUT
    data = LazyAttribute(
        lambda _obj: {"label": fake.word(), "format": InputNodeFormat.TXT},
    )
    position_x = 0.0
    position_y = 0.0
