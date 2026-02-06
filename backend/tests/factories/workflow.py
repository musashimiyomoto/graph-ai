"""Workflow model factory."""

from factory.declarations import LazyAttribute

from models.workflow import Workflow
from tests.factories.base import AsyncSQLAlchemyModelFactory, fake


class WorkflowFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating Workflow instances."""

    class Meta:
        """Factory meta configuration."""

        model = Workflow

    owner_id = None
    name = LazyAttribute(lambda _obj: f"workflow-{fake.word()}")
