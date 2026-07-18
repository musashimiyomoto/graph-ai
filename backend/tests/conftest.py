"""Pytest fixtures for backend tests."""

from collections.abc import AsyncGenerator, Generator
from types import SimpleNamespace

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from api.dependencies import db, qdrant, queue, quota, rate_limit
from api.dependencies import redis as redis_dependency
from db.models import Base
from main import app
from settings import postgres_settings


@pytest.fixture(scope="session", autouse=True)
def fast_password_hashing() -> Generator[None, None, None]:
    """Use bcrypt's minimum cost while preserving real hashing in tests."""
    original_gensalt = bcrypt.gensalt

    def fast_gensalt(rounds: int = 12, prefix: bytes = b"2b") -> bytes:
        """Generate a valid low-cost salt regardless of the production default."""
        del rounds
        return original_gensalt(rounds=4, prefix=prefix)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(bcrypt, "gensalt", fast_gensalt)
    try:
        yield
    finally:
        monkeypatch.undo()


class _NoopArqPool:
    """Stand-in ARQ pool that drops enqueued jobs during tests."""

    async def enqueue_job(self, *args: object, **kwargs: object) -> SimpleNamespace:
        """Accept an enqueue call and return a job stub carrying a job_id."""
        del args, kwargs
        return SimpleNamespace(job_id="test-job-id")


class _NoopRedisClient:
    """Stand-in Redis client so tests need no real Redis for health checks."""

    async def ping(self) -> bool:
        """Report healthy without a real connection."""
        return True


class _NoopQdrantClient:
    """Stand-in Qdrant client so tests need no real Qdrant for health checks."""

    async def get_collections(self) -> None:
        """Report healthy without a real connection."""
        return


@pytest_asyncio.fixture(scope="session")
async def postgres_container() -> AsyncGenerator[PostgresContainer, None]:
    """Spin up a Postgres container for the test session."""
    with PostgresContainer(image=postgres_settings.image, driver="asyncpg") as postgres:
        yield postgres


@pytest_asyncio.fixture(scope="session")
async def test_engine(
    postgres_container: PostgresContainer,
) -> AsyncGenerator[AsyncEngine, None]:
    """Create one database engine and schema for the entire test session."""
    engine = create_async_engine(
        url=postgres_container.get_connection_url(),
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session_factory(
    test_engine: AsyncEngine,
    request: pytest.FixtureRequest,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Provide isolated sessions using rollback for the common test path."""
    if request.node.get_closest_marker("committed_db") is not None:
        session_factory = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )
        try:
            yield session_factory
        finally:
            tables = list(Base.metadata.sorted_tables)
            if tables:
                async with test_engine.begin() as connection:
                    preparer = connection.dialect.identifier_preparer
                    names = ", ".join(preparer.format_table(table) for table in tables)
                    await connection.execute(
                        text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE")
                    )
        return

    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session_factory = async_sessionmaker(
            connection,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session_factory
        finally:
            if transaction.is_active:
                await transaction.rollback()


@pytest_asyncio.fixture(scope="function")
async def test_session(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Provide the primary database session for a test."""
    session = test_session_factory()
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture(scope="function")
async def test_client(
    test_session: AsyncSession,
    test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP client with the test session injected."""

    def override_get_session() -> AsyncSession:
        """Return the test session for dependency overrides."""
        return test_session

    def override_get_session_factory() -> async_sessionmaker[AsyncSession]:
        """Return a session factory bound to the test engine."""
        return test_session_factory

    def override_get_arq_pool() -> _NoopArqPool:
        """Return a no-op ARQ pool so tests need no Redis."""
        return _NoopArqPool()

    def override_get_redis_client() -> _NoopRedisClient:
        """Return a no-op Redis client so tests need no real Redis."""
        return _NoopRedisClient()

    def override_get_qdrant_client() -> _NoopQdrantClient:
        """Return a no-op Qdrant client so tests need no real Qdrant."""
        return _NoopQdrantClient()

    async def override_rate_limit() -> None:
        """Bypass rate limiting so repeated test requests never 429."""
        return

    async def override_quota() -> None:
        """Bypass the execution quota gate so tests never 429 on volume."""
        return

    app.dependency_overrides[db.get_session] = override_get_session
    app.dependency_overrides[db.get_session_factory] = override_get_session_factory
    app.dependency_overrides[queue.get_arq_pool] = override_get_arq_pool
    app.dependency_overrides[redis_dependency.get_redis_client] = (
        override_get_redis_client
    )
    app.dependency_overrides[qdrant.get_qdrant_client] = override_get_qdrant_client
    app.dependency_overrides[rate_limit.enforce_login_rate_limit] = override_rate_limit
    app.dependency_overrides[rate_limit.enforce_register_rate_limit] = (
        override_rate_limit
    )
    app.dependency_overrides[quota.enforce_execution_quota] = override_quota

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
