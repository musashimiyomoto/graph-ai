"""Unified connection and OAuth 2.0 business logic."""

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Connection
from db.repositories import ConnectionOAuthStateRepository, ConnectionRepository
from enums import ConnectionAuthType, ConnectionStatus
from exceptions import (
    BlockedURLError,
    ConnectionAlreadyExistsError,
    ConnectionNotFoundError,
    ConnectionRevokedError,
    OAuthExchangeError,
    OAuthStateError,
)
from schemas import (
    ConnectionCreate,
    ConnectionOAuthCallbackResponse,
    ConnectionOAuthStart,
    ConnectionOAuthStartResponse,
    ConnectionResponse,
)
from usecases.audit import AuditEvent, AuditUsecase
from utils.encryption import decrypt, encrypt
from utils.network import blocked_url_reason

_OAUTH_STATE_TTL = timedelta(minutes=10)
_TOKEN_EXPIRY_SKEW = timedelta(seconds=60)
_HTTP_TIMEOUT_SECONDS = 15.0
_MAX_ERROR_LENGTH = 1000


def _state_hash(state: str) -> str:
    """Hash a bearer OAuth state before persistence."""
    return hashlib.sha256(state.encode()).hexdigest()


def _pkce_challenge(verifier: str) -> str:
    """Build an RFC 7636 S256 code challenge."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _bounded_error(message: str) -> str:
    """Bound provider errors before durable storage."""
    return message[:_MAX_ERROR_LENGTH]


def connection_response(connection: Connection) -> ConnectionResponse:
    """Build public metadata without exposing decrypted credentials."""
    credentials = json.loads(decrypt(connection.credentials))
    return ConnectionResponse(
        id=connection.id,
        user_id=connection.user_id,
        name=connection.name,
        provider=connection.provider,
        auth_type=connection.auth_type,
        status=connection.status,
        config=connection.config,
        scopes=connection.scopes,
        has_credentials=bool(credentials),
        token_expires_at=connection.token_expires_at,
        last_used_at=connection.last_used_at,
        last_checked_at=connection.last_checked_at,
        last_error=connection.last_error,
        revoked_at=connection.revoked_at,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


class ConnectionUsecase:
    """Manage encrypted API-key and OAuth connections."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialize repositories and an optional test/provider HTTP client."""
        self._repository = ConnectionRepository()
        self._oauth_state_repository = ConnectionOAuthStateRepository()
        self._audit_usecase = AuditUsecase()
        self._http_client = http_client

    async def create_connection(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        data: ConnectionCreate,
    ) -> ConnectionResponse:
        """Validate, encrypt, and create one reusable connection."""
        await self._validate_server_urls(data)
        config, credentials = self._creation_payload(data)
        status = (
            ConnectionStatus.ACTIVE
            if data.auth_type is ConnectionAuthType.API_KEY
            else ConnectionStatus.PENDING
        )
        try:
            created = await self._repository.create(
                session=session,
                data={
                    "user_id": user_id,
                    "name": data.name,
                    "provider": data.provider,
                    "auth_type": data.auth_type,
                    "status": status,
                    "config": config,
                    "scopes": data.scopes,
                    "credentials": encrypt(json.dumps(credentials)),
                },
            )
        except IntegrityError as exc:
            await session.rollback()
            raise ConnectionAlreadyExistsError from exc
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="connection.create",
                entity_type="connection",
                entity_id=created.id,
                metadata={
                    "provider": created.provider,
                    "auth_type": created.auth_type.value,
                    "scopes": created.scopes,
                },
            ),
        )
        await session.commit()
        return connection_response(created)

    async def list_connections(
        self, *, session: AsyncSession, user_id: int
    ) -> list[ConnectionResponse]:
        """List owned connection metadata without secrets."""
        connections = await self._repository.get_all(session=session, user_id=user_id)
        return [connection_response(item) for item in connections]

    async def start_oauth(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        connection_id: int,
        data: ConnectionOAuthStart,
    ) -> ConnectionOAuthStartResponse:
        """Create a single-use OAuth state and return the provider URL."""
        connection = await self._get_owned(session, user_id, connection_id)
        if connection.auth_type is not ConnectionAuthType.OAUTH2:
            raise OAuthStateError(message="Connection does not use OAuth 2.0")
        config = connection.config
        authorization_url = config.get("authorization_url")
        client_id = config.get("client_id")
        if not isinstance(authorization_url, str) or not isinstance(client_id, str):
            raise OAuthStateError(
                message="OAuth connection configuration is incomplete"
            )

        now = datetime.now(tz=UTC)
        await self._oauth_state_repository.delete_expired(session=session, now=now)
        await self._oauth_state_repository.delete_all(
            session=session, connection_id=connection.id
        )
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        expires_at = now + _OAUTH_STATE_TTL
        await self._oauth_state_repository.create(
            session=session,
            data={
                "connection_id": connection.id,
                "state_hash": _state_hash(state),
                "code_verifier": encrypt(verifier),
                "redirect_uri": data.redirect_uri,
                "expires_at": expires_at,
            },
        )
        await self._repository.update_by(
            session=session,
            id=connection.id,
            data={
                "status": ConnectionStatus.PENDING,
                "revoked_at": None,
                "last_error": None,
            },
        )
        await session.commit()
        query = dict(parse_qsl(urlparse(authorization_url).query))
        query.update(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": data.redirect_uri,
                "state": state,
                "code_challenge": _pkce_challenge(verifier),
                "code_challenge_method": "S256",
            }
        )
        if connection.scopes:
            query["scope"] = " ".join(connection.scopes)
        parsed = urlparse(authorization_url)
        return ConnectionOAuthStartResponse(
            authorization_url=urlunparse(parsed._replace(query=urlencode(query))),
            expires_at=expires_at,
        )

    async def complete_oauth(
        self,
        *,
        session: AsyncSession,
        state: str,
        code: str,
    ) -> ConnectionOAuthCallbackResponse:
        """Consume OAuth state and exchange an authorization code for tokens."""
        now = datetime.now(tz=UTC)
        oauth_state = await self._oauth_state_repository.get_by_hash_for_update(
            session=session, state_hash=_state_hash(state)
        )
        if oauth_state is None or oauth_state.expires_at <= now:
            if oauth_state is not None:
                await self._oauth_state_repository.delete_by(
                    session=session, id=oauth_state.id
                )
                await session.commit()
            raise OAuthStateError
        connection = await self._repository.get_for_update(
            session=session, connection_id=oauth_state.connection_id
        )
        if connection is None or connection.auth_type is not ConnectionAuthType.OAUTH2:
            raise OAuthStateError
        await self._oauth_state_repository.delete_by(session=session, id=oauth_state.id)
        try:
            token_payload = await self._token_request(
                connection=connection,
                form={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": oauth_state.redirect_uri,
                    "client_id": connection.config["client_id"],
                    "code_verifier": decrypt(oauth_state.code_verifier),
                    **self._client_secret_form(connection),
                },
            )
            self._apply_token_payload(
                connection=connection,
                payload=token_payload,
                now=now,
            )
        except OAuthExchangeError as exc:
            connection.status = ConnectionStatus.UNHEALTHY
            connection.last_error = _bounded_error(exc.message)
            connection.last_checked_at = now
            await session.commit()
            raise
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=connection.user_id,
                action="connection.oauth_authorize",
                entity_type="connection",
                entity_id=connection.id,
                metadata={"provider": connection.provider, "scopes": connection.scopes},
            ),
        )
        await session.commit()
        return ConnectionOAuthCallbackResponse(
            connection_id=connection.id,
            status=connection.status,
        )

    async def refresh_oauth(
        self, *, session: AsyncSession, user_id: int, connection_id: int
    ) -> ConnectionResponse:
        """Explicitly refresh one owned OAuth access token."""
        connection = await self._get_owned_for_update(session, user_id, connection_id)
        if connection.auth_type is not ConnectionAuthType.OAUTH2:
            raise OAuthExchangeError(message="Connection does not use OAuth 2.0")
        if connection.status is ConnectionStatus.REVOKED:
            raise ConnectionRevokedError
        try:
            await self._refresh_locked(session=session, connection=connection)
        except OAuthExchangeError:
            await session.commit()
            raise
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="connection.oauth_refresh",
                entity_type="connection",
                entity_id=connection.id,
            ),
        )
        return await self._commit_response(session=session, connection=connection)

    async def check_health(
        self, *, session: AsyncSession, user_id: int, connection_id: int
    ) -> ConnectionResponse:
        """Refresh credentials if needed and run the configured health request."""
        connection = await self._get_owned_for_update(session, user_id, connection_id)
        if connection.status is ConnectionStatus.REVOKED:
            raise ConnectionRevokedError
        now = datetime.now(tz=UTC)
        health_url = connection.config.get("health_url")
        if isinstance(health_url, str):
            reason = await blocked_url_reason(health_url)
            if reason is not None:
                raise BlockedURLError(message=reason)
        try:
            headers = await self._authorization_headers_locked(
                session=session, connection=connection, now=now
            )
            if isinstance(health_url, str):
                response = await self._request("GET", health_url, headers=headers)
                response.raise_for_status()
            connection.status = ConnectionStatus.ACTIVE
            connection.last_error = None
        except (OAuthExchangeError, httpx.HTTPError) as exc:
            connection.status = ConnectionStatus.UNHEALTHY
            connection.last_error = _bounded_error(str(exc))
        connection.last_checked_at = now
        return await self._commit_response(session=session, connection=connection)

    async def revoke_connection(
        self, *, session: AsyncSession, user_id: int, connection_id: int
    ) -> ConnectionResponse:
        """Attempt provider revocation, then irreversibly clear local credentials."""
        connection = await self._get_owned_for_update(session, user_id, connection_id)
        credentials = self._credentials(connection)
        provider_error: str | None = None
        revocation_url = connection.config.get("revocation_url")
        token = credentials.get("refresh_token") or credentials.get("access_token")
        if isinstance(revocation_url, str) and isinstance(token, str):
            reason = await blocked_url_reason(revocation_url)
            if reason is not None:
                raise BlockedURLError(message=reason)
            try:
                response = await self._request(
                    "POST",
                    revocation_url,
                    data={
                        "token": token,
                        "client_id": connection.config.get("client_id", ""),
                        **self._client_secret_form(connection),
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                provider_error = _bounded_error(f"Provider revocation failed: {exc}")
        now = datetime.now(tz=UTC)
        connection.credentials = encrypt("{}")
        connection.status = ConnectionStatus.REVOKED
        connection.token_expires_at = None
        connection.revoked_at = now
        connection.last_checked_at = now
        connection.last_error = provider_error
        await self._oauth_state_repository.delete_all(
            session=session, connection_id=connection.id
        )
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="connection.revoke",
                entity_type="connection",
                entity_id=connection.id,
                metadata={"provider_revocation_error": provider_error},
            ),
        )
        return await self._commit_response(session=session, connection=connection)

    async def delete_connection(
        self, *, session: AsyncSession, user_id: int, connection_id: int
    ) -> None:
        """Delete one owned connection and its OAuth states."""
        deleted = await self._repository.delete_by(
            session=session, id=connection_id, user_id=user_id
        )
        if not deleted:
            raise ConnectionNotFoundError
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="connection.delete",
                entity_type="connection",
                entity_id=connection_id,
            ),
        )
        await session.commit()

    async def _validate_server_urls(self, data: ConnectionCreate) -> None:
        """Reject unsafe token, revocation, and health endpoints before storage."""
        for url in (data.token_url, data.revocation_url, data.health_url):
            if url is None:
                continue
            reason = await blocked_url_reason(url)
            if reason is not None:
                raise BlockedURLError(message=reason)

    @staticmethod
    async def _commit_response(
        *, session: AsyncSession, connection: Connection
    ) -> ConnectionResponse:
        """Commit, reload server-updated columns, and build a safe response."""
        await session.commit()
        await session.refresh(connection)
        return connection_response(connection)

    @staticmethod
    def _creation_payload(data: ConnectionCreate) -> tuple[dict, dict[str, str]]:
        """Split safe configuration from the encrypted credential envelope."""
        if data.auth_type is ConnectionAuthType.API_KEY:
            if data.api_key is None:
                message = "Validated API-key connection is missing api_key"
                raise RuntimeError(message)
            return (
                {
                    "header_name": data.header_name,
                    "prefix": data.prefix,
                    "health_url": data.health_url,
                },
                {"api_key": data.api_key.get_secret_value()},
            )
        return (
            {
                "authorization_url": data.authorization_url,
                "token_url": data.token_url,
                "revocation_url": data.revocation_url,
                "health_url": data.health_url,
                "client_id": data.client_id,
            },
            {
                "client_secret": (
                    data.client_secret.get_secret_value()
                    if data.client_secret is not None
                    else ""
                )
            },
        )

    async def _get_owned(
        self, session: AsyncSession, user_id: int, connection_id: int
    ) -> Connection:
        """Return an owned connection or raise not-found."""
        connection = await self._repository.get_by(
            session=session, id=connection_id, user_id=user_id
        )
        if connection is None:
            raise ConnectionNotFoundError
        return connection

    async def _get_owned_for_update(
        self, session: AsyncSession, user_id: int, connection_id: int
    ) -> Connection:
        """Lock and authorize a connection for a credential transition."""
        connection = await self._repository.get_for_update(
            session=session, connection_id=connection_id
        )
        if connection is None or connection.user_id != user_id:
            raise ConnectionNotFoundError
        return connection

    @staticmethod
    def _credentials(connection: Connection) -> dict[str, Any]:
        """Decrypt one credential envelope at the narrow use boundary."""
        payload = json.loads(decrypt(connection.credentials))
        return payload if isinstance(payload, dict) else {}

    def _client_secret_form(self, connection: Connection) -> dict[str, str]:
        """Return a client secret form field only for confidential clients."""
        client_secret = self._credentials(connection).get("client_secret")
        return (
            {"client_secret": client_secret}
            if isinstance(client_secret, str) and client_secret
            else {}
        )

    async def _token_request(
        self, *, connection: Connection, form: dict[str, str]
    ) -> dict[str, Any]:
        """POST to the safe configured token endpoint and parse OAuth JSON."""
        token_url = connection.config.get("token_url")
        if not isinstance(token_url, str):
            raise OAuthExchangeError(message="OAuth token endpoint is missing")
        reason = await blocked_url_reason(token_url)
        if reason is not None:
            raise BlockedURLError(message=reason)
        try:
            response = await self._request(
                "POST",
                token_url,
                data=form,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OAuthExchangeError from exc
        if not isinstance(payload, dict) or not isinstance(
            payload.get("access_token"), str
        ):
            raise OAuthExchangeError(message="OAuth response omitted access_token")
        return payload

    def _apply_token_payload(
        self,
        *,
        connection: Connection,
        payload: dict[str, Any],
        now: datetime,
    ) -> None:
        """Encrypt refreshed tokens and update safe lifecycle metadata."""
        previous = self._credentials(connection)
        credentials = {
            "client_secret": previous.get("client_secret", ""),
            "access_token": payload["access_token"],
            "refresh_token": payload.get("refresh_token")
            or previous.get("refresh_token"),
            "token_type": payload.get("token_type", "Bearer"),
        }
        connection.credentials = encrypt(json.dumps(credentials))
        expires_in = payload.get("expires_in")
        connection.token_expires_at = (
            now + timedelta(seconds=max(0, float(expires_in)))
            if isinstance(expires_in, int | float)
            else None
        )
        granted_scope = payload.get("scope")
        if isinstance(granted_scope, str):
            connection.scopes = granted_scope.split()
        connection.status = ConnectionStatus.ACTIVE
        connection.revoked_at = None
        connection.last_error = None
        connection.last_used_at = now

    async def _refresh_locked(
        self, *, session: AsyncSession, connection: Connection
    ) -> None:
        """Refresh OAuth tokens while the caller holds the connection row lock."""
        del session
        credentials = self._credentials(connection)
        refresh_token = credentials.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token:
            raise OAuthExchangeError(message="OAuth refresh token is unavailable")
        now = datetime.now(tz=UTC)
        try:
            payload = await self._token_request(
                connection=connection,
                form={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": connection.config["client_id"],
                    **self._client_secret_form(connection),
                },
            )
        except OAuthExchangeError as exc:
            connection.status = ConnectionStatus.UNHEALTHY
            connection.last_error = _bounded_error(exc.message)
            connection.last_checked_at = now
            raise
        self._apply_token_payload(connection=connection, payload=payload, now=now)

    async def _authorization_headers_locked(
        self,
        *,
        session: AsyncSession,
        connection: Connection,
        now: datetime,
    ) -> dict[str, str]:
        """Resolve auth headers, transparently refreshing expiring OAuth tokens."""
        credentials = self._credentials(connection)
        if connection.auth_type is ConnectionAuthType.API_KEY:
            api_key = credentials.get("api_key")
            if not isinstance(api_key, str):
                raise ConnectionRevokedError
            prefix = connection.config.get("prefix")
            value = f"{prefix} {api_key}".strip() if prefix else api_key
            header_name = connection.config.get("header_name", "Authorization")
            connection.last_used_at = now
            return {str(header_name): value}
        if (
            connection.token_expires_at is not None
            and connection.token_expires_at <= now + _TOKEN_EXPIRY_SKEW
        ):
            await self._refresh_locked(session=session, connection=connection)
            credentials = self._credentials(connection)
        access_token = credentials.get("access_token")
        if not isinstance(access_token, str):
            raise OAuthExchangeError(message="OAuth access token is unavailable")
        token_type = credentials.get("token_type", "Bearer")
        connection.last_used_at = now
        return {"Authorization": f"{token_type} {access_token}"}

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Perform one provider request through an injected or short-lived client."""
        if self._http_client is not None:
            return await self._http_client.request(
                method, url, headers=headers, data=data
            )
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            return await client.request(method, url, headers=headers, data=data)
