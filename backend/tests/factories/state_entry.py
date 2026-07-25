"""State entry model factory."""

from factory.declarations import LazyFunction

from db.models import StateEntry
from enums import StateScope
from tests.factories.base import AsyncSQLAlchemyModelFactory


class StateEntryFactory(AsyncSQLAlchemyModelFactory):
    """Factory for current typed durable state values."""

    class Meta:
        """Factory meta configuration."""

        model = StateEntry

    owner_id = None
    workflow_id = None
    scope = StateScope.WORKFLOW
    scope_ref = "1"
    key = "test"
    value = LazyFunction(
        lambda: {
            "kind": "text",
            "value": "value",
            "artifact": None,
            "metadata": {},
        }
    )
    version = 1
