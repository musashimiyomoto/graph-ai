"""Pytest fixtures for backend tests."""

from collections.abc import AsyncGenerator
from types import SimpleNamespace

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
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


@pytest_asyncio.fixture(scope="function")
async def test_engine(
    postgres_container: PostgresContainer,
) -> AsyncGenerator[AsyncEngine, None]:
    """Create a fresh database engine for each test."""
    engine = create_async_engine(
        url=postgres_container.get_connection_url(),
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for tests."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def test_client(
    test_session: AsyncSession, test_engine: AsyncEngine
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP client with the test session injected."""

    def override_get_session() -> AsyncSession:
        """Return the test session for dependency overrides."""
        return test_session

    def override_get_session_factory() -> async_sessionmaker[AsyncSession]:
        """Return a session factory bound to the test engine."""
        return async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )

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
