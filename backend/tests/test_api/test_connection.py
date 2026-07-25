"""Unified encrypted connection and OAuth API tests."""

import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from api.dependencies import connection as connection_dependency
from db.models import Connection, ConnectionOAuthState
from enums import ConnectionAuthType, ConnectionStatus
from main import app
from tests.factories import ConnectionFactory
from tests.test_api.base import BaseTestCase
from usecases import ConnectionUsecase
from utils.encryption import decrypt, encrypt


async def _allow_public_url(_: str) -> None:
    """Treat test provider URLs as public without DNS access."""
    return


def _require(*, condition: bool, message: str) -> None:
    """Fail with a readable message when a tested contract is not met."""
    if not condition:
        pytest.fail(message)


class TestConnectionAPI(BaseTestCase):
    """Tests for common API-key and OAuth connection behavior."""

    @pytest.mark.asyncio
    async def test_api_key_is_write_only_and_used_for_health_check(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """API keys stay encrypted but produce the configured outbound header."""
        monkeypatch.setattr("usecases.connection.blocked_url_reason", _allow_public_url)
        observed_authorization: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            observed_authorization.append(request.headers.get("Authorization"))
            return httpx.Response(status_code=HTTPStatus.NO_CONTENT)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        app.dependency_overrides[connection_dependency.get_connection_usecase] = (
            lambda: ConnectionUsecase(http_client=client)
        )
        _, headers = await self.create_user_and_get_token()
        raw_key = "api-key-that-must-never-leak"

        created = await self.client.post(
            url="/connections",
            headers=headers,
            json={
                "name": "Search API",
                "provider": "search",
                "auth_type": "api_key",
                "api_key": raw_key,
                "health_url": "https://provider.example/health",
            },
        )
        data = await self.assert_response_dict(response=created)
        if data["status"] != "active" or not data["has_credentials"]:
            pytest.fail("API-key connection was not active after creation")
        if raw_key in created.text:
            pytest.fail("Connection response exposed the API key")

        row = await self.session.scalar(
            select(Connection).where(Connection.id == data["id"])
        )
        if row is None:
            pytest.fail("Connection was not persisted")
            return
        if raw_key in row.credentials:
            pytest.fail("API key was stored in plaintext")
        if json.loads(decrypt(row.credentials))["api_key"] != raw_key:
            pytest.fail("Encrypted API key could not be recovered internally")

        health = await self.client.post(
            url=f"/connections/{data['id']}/health", headers=headers
        )
        health_data = await self.assert_response_dict(response=health)
        if health_data["status"] != "active" or not health_data["last_used_at"]:
            pytest.fail("Health check did not update connection usage metadata")
        if observed_authorization != [f"Bearer {raw_key}"]:
            pytest.fail("Health check used the wrong authorization header")
        await client.aclose()

    @pytest.mark.asyncio
    async def test_oauth_pkce_callback_refresh_and_revoke(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OAuth state is hashed/single-use and tokens refresh then revoke safely."""
        monkeypatch.setattr("usecases.connection.blocked_url_reason", _allow_public_url)
        token_grants: list[str] = []
        revoked_tokens: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            form = parse_qs(request.content.decode())
            if request.url.path == "/token":
                grant = form.get("grant_type", [""])[0]
                token_grants.append(grant)
                if grant == "authorization_code":
                    return httpx.Response(
                        status_code=HTTPStatus.OK,
                        json={
                            "access_token": "access-one",
                            "refresh_token": "refresh-one",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                            "scope": "files.read files.write",
                        },
                    )
                return httpx.Response(
                    status_code=HTTPStatus.OK,
                    json={
                        "access_token": "access-two",
                        "refresh_token": "refresh-two",
                        "expires_in": 7200,
                    },
                )
            if request.url.path == "/revoke":
                revoked_tokens.append(form.get("token", [""])[0])
                return httpx.Response(status_code=HTTPStatus.OK)
            return httpx.Response(status_code=HTTPStatus.NOT_FOUND)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        app.dependency_overrides[connection_dependency.get_connection_usecase] = (
            lambda: ConnectionUsecase(http_client=client)
        )
        _, headers = await self.create_user_and_get_token()

        created = await self.client.post(
            url="/connections",
            headers=headers,
            json={
                "name": "Drive OAuth",
                "provider": "drive",
                "auth_type": "oauth2",
                "authorization_url": "https://oauth.example/authorize",
                "token_url": "https://oauth.example/token",
                "revocation_url": "https://oauth.example/revoke",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "scopes": ["files.read", "files.write"],
            },
        )
        created_data = await self.assert_response_dict(response=created)
        _require(
            condition=created_data["status"] == "pending",
            message="OAuth connection did not start pending authorization",
        )

        started = await self.client.post(
            url=f"/connections/{created_data['id']}/oauth/start",
            headers=headers,
            json={"redirect_uri": "https://app.example/api/connections/oauth/callback"},
        )
        started_data = await self.assert_response_dict(response=started)
        query = parse_qs(urlparse(started_data["authorization_url"]).query)
        state = query.get("state", [""])[0]
        _require(
            condition=bool(state) and query.get("code_challenge_method") == ["S256"],
            message="OAuth start omitted state or PKCE S256 challenge",
        )
        oauth_state = await self.session.scalar(select(ConnectionOAuthState))
        _require(
            condition=oauth_state is not None and oauth_state.state_hash != state,
            message="Raw OAuth state was persisted instead of its hash",
        )

        callback = await self.client.get(
            url="/connections/oauth/callback",
            params={"state": state, "code": "authorization-code"},
        )
        callback_data = await self.assert_response_dict(response=callback)
        _require(
            condition=callback_data["status"] == "active",
            message="OAuth callback did not activate the connection",
        )
        replay = await self.client.get(
            url="/connections/oauth/callback",
            params={"state": state, "code": "authorization-code"},
        )
        _require(
            condition=replay.status_code == HTTPStatus.BAD_REQUEST,
            message="OAuth state could be replayed",
        )

        refreshed = await self.client.post(
            url=f"/connections/{created_data['id']}/refresh", headers=headers
        )
        refreshed_data = await self.assert_response_dict(response=refreshed)
        _require(
            condition=refreshed_data["status"] == "active",
            message="OAuth refresh did not keep the connection active",
        )
        _require(
            condition=token_grants == ["authorization_code", "refresh_token"],
            message="OAuth token endpoint received the wrong grant sequence",
        )

        revoked = await self.client.post(
            url=f"/connections/{created_data['id']}/revoke", headers=headers
        )
        revoked_data = await self.assert_response_dict(response=revoked)
        _require(
            condition=revoked_data["status"] == "revoked"
            and not revoked_data["has_credentials"],
            message="Revocation did not clear local credentials",
        )
        _require(
            condition=revoked_tokens == ["refresh-two"],
            message="Provider revocation did not receive the newest refresh token",
        )
        await client.aclose()

    @pytest.mark.asyncio
    async def test_connections_are_tenant_owned(self) -> None:
        """Another tenant cannot list or delete a connection."""
        owner, owner_headers = await self.create_user_and_get_token()
        connection = await ConnectionFactory.create_async(
            session=self.session, user_id=owner["id"]
        )
        _, other_headers = await self.create_user_and_get_token()

        listed = await self.client.get(url="/connections", headers=other_headers)
        if await self.assert_response_list(response=listed):
            pytest.fail("Another tenant could list the connection")
        deleted = await self.client.delete(
            url=f"/connections/{connection.id}", headers=other_headers
        )
        if deleted.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Another tenant could address the connection")

        owner_list = await self.client.get(url="/connections", headers=owner_headers)
        rows = await self.assert_response_list(response=owner_list)
        if [row["id"] for row in rows] != [connection.id]:
            pytest.fail("Owner could not list the connection")

    @pytest.mark.asyncio
    async def test_failed_explicit_refresh_persists_unhealthy_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rejected refresh records durable health metadata before returning."""
        monkeypatch.setattr("usecases.connection.blocked_url_reason", _allow_public_url)

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=HTTPStatus.UNAUTHORIZED)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        app.dependency_overrides[connection_dependency.get_connection_usecase] = (
            lambda: ConnectionUsecase(http_client=client)
        )
        user, headers = await self.create_user_and_get_token()
        connection = await ConnectionFactory.create_async(
            session=self.session,
            user_id=user["id"],
            auth_type=ConnectionAuthType.OAUTH2,
            status=ConnectionStatus.ACTIVE,
            config={
                "authorization_url": "https://oauth.example/authorize",
                "token_url": "https://oauth.example/token",
                "revocation_url": None,
                "health_url": None,
                "client_id": "client-id",
            },
            credentials=encrypt(
                json.dumps(
                    {
                        "access_token": "expired-access",
                        "refresh_token": "rejected-refresh",
                        "token_type": "Bearer",
                    }
                )
            ),
            token_expires_at=datetime.now(tz=UTC) - timedelta(minutes=1),
        )

        response = await self.client.post(
            url=f"/connections/{connection.id}/refresh", headers=headers
        )
        _require(
            condition=response.status_code == HTTPStatus.BAD_GATEWAY,
            message="Rejected OAuth refresh returned the wrong status",
        )
        await self.session.refresh(connection)
        _require(
            condition=connection.status.value == "unhealthy"
            and connection.last_checked_at is not None
            and connection.last_error is not None,
            message="Rejected OAuth refresh did not persist unhealthy metadata",
        )
        await client.aclose()
