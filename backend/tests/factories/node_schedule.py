"""Node schedule model factory."""

from db.models import NodeSchedule
from tests.factories.base import AsyncSQLAlchemyModelFactory


class NodeScheduleFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating NodeSchedule instances."""

    class Meta:
        """Factory meta configuration."""

        model = NodeSchedule

    node_id = None
    cron_expression = "* * * * *"
