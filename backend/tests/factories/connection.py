"""Unified connection model factory."""

import json
from uuid import uuid4

from factory.declarations import LazyFunction

from db.models import Connection
from enums import ConnectionAuthType, ConnectionStatus
from tests.factories.base import AsyncSQLAlchemyModelFactory
from utils.encryption import encrypt


class ConnectionFactory(AsyncSQLAlchemyModelFactory):
    """Factory for reusable encrypted connections."""

    class Meta:
        """Factory meta configuration."""

        model = Connection

    user_id = None
    name = LazyFunction(lambda: f"Connection {uuid4().hex[:8]}")
    provider = "generic"
    auth_type = ConnectionAuthType.API_KEY
    status = ConnectionStatus.ACTIVE
    config = LazyFunction(
        lambda: {
            "header_name": "Authorization",
            "prefix": "Bearer",
            "health_url": None,
        }
    )
    scopes = LazyFunction(list)
    credentials = LazyFunction(
        lambda: encrypt(json.dumps({"api_key": "factory-secret"}))
    )
