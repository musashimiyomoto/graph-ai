"""Pytest fixtures for backend tests."""

from collections.abc import AsyncGenerator, Generator
from types import SimpleNamespace
from urllib.parse import urlsplit

import bcrypt
import pytest
import pytest_asyncio
from arq.connections import RedisSettings
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from xdist.workermanage import WorkerController

from api.dependencies import db, qdrant, queue, quota, rate_limit
from api.dependencies import redis as redis_dependency
from db.models import Base
from main import app
from settings import postgres_settings

_POSTGRES_URL_WORKER_KEY = "graph_ai_postgres_url"
_REDIS_URL_WORKER_KEY = "graph_ai_redis_url"
_shared_postgres_container: PostgresContainer | None = None
_shared_redis_container: RedisContainer | None = None


def _new_postgres_container() -> PostgresContainer:
    """Build an ephemeral PostgreSQL tuned for test throughput."""
    return (
        PostgresContainer(image=postgres_settings.image, driver="asyncpg")
        .with_command(
            [
                "postgres",
                "-c",
                "fsync=off",
                "-c",
                "full_page_writes=off",
                "-c",
                "synchronous_commit=off",
            ]
        )
        .with_kwargs(tmpfs={"/var/lib/postgresql/data": "rw"})
    )


def _new_redis_container() -> RedisContainer:
    """Build an ephemeral Redis with enough logical worker databases."""
    return RedisContainer(image="redis:7.4-alpine").with_command(
        [
            "redis-server",
            "--databases",
            "256",
            "--save",
            "",
            "--appendonly",
            "no",
        ]
    )


def pytest_configure_node(node: WorkerController) -> None:
    """Give xdist workers isolated databases on shared test servers."""
    global _shared_postgres_container, _shared_redis_container  # noqa: PLW0603

    if _shared_postgres_container is None:
        container = _new_postgres_container()
        container.start()
        _shared_postgres_container = container

    worker_id = node.gateway.id
    if not worker_id.startswith("gw") or not worker_id[2:].isdigit():
        message = f"Unexpected xdist worker ID: {worker_id}"
        raise RuntimeError(message)
    worker_number = int(worker_id[2:])

    database_name = f"graph_ai_test_{worker_id}"
    creation = _shared_postgres_container.exec(
        [
            "createdb",
            "-U",
            _shared_postgres_container.username,
            database_name,
        ]
    )
    if creation.exit_code != 0:
        detail = creation.output.decode(errors="replace")
        message = f"Could not create test database {database_name}: {detail}"
        raise RuntimeError(message)

    base_url = _shared_postgres_container.get_connection_url()
    node.workerinput[_POSTGRES_URL_WORKER_KEY] = base_url.rsplit("/", 1)[0] + (
        f"/{database_name}"
    )

    if _shared_redis_container is None:
        redis_container = _new_redis_container()
        redis_container.start()
        _shared_redis_container = redis_container

    redis_host = _shared_redis_container.get_container_host_ip()
    redis_port = _shared_redis_container.get_exposed_port(6379)
    node.workerinput[_REDIS_URL_WORKER_KEY] = (
        f"redis://{redis_host}:{redis_port}/{worker_number}"
    )


def pytest_unconfigure(config: pytest.Config) -> None:
    """Stop controller-owned data services after every worker has exited."""
    del config
    global _shared_postgres_container, _shared_redis_container  # noqa: PLW0603

    if _shared_redis_container is not None:
        _shared_redis_container.stop()
        _shared_redis_container = None

    if _shared_postgres_container is not None:
        _shared_postgres_container.stop()
        _shared_postgres_container = None


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
        del args
        return SimpleNamespace(job_id=kwargs.get("_job_id", "test-job-id"))


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


@pytest.fixture(scope="session")
def test_database_url(request: pytest.FixtureRequest) -> Generator[str, None, None]:
    """Provide a private database URL from serial or controller-owned Postgres."""
    worker_input = getattr(request.config, "workerinput", None)
    if isinstance(worker_input, dict):
        database_url = worker_input.get(_POSTGRES_URL_WORKER_KEY)
        if not isinstance(database_url, str):
            message = "xdist controller did not provide a PostgreSQL URL"
            raise TypeError(message)
        yield database_url
        return

    with _new_postgres_container() as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def test_redis_url(request: pytest.FixtureRequest) -> Generator[str, None, None]:
    """Provide an isolated logical Redis database for the current worker."""
    worker_input = getattr(request.config, "workerinput", None)
    if isinstance(worker_input, dict):
        redis_url = worker_input.get(_REDIS_URL_WORKER_KEY)
        if not isinstance(redis_url, str):
            message = "xdist controller did not provide a Redis URL"
            raise TypeError(message)
        yield redis_url
        return

    with _new_redis_container() as redis_container:
        redis_host = redis_container.get_container_host_ip()
        redis_port = redis_container.get_exposed_port(6379)
        yield f"redis://{redis_host}:{redis_port}/0"


@pytest_asyncio.fixture
async def test_redis(test_redis_url: str) -> AsyncGenerator[Redis, None]:
    """Yield a clean real Redis client without starting a per-test container."""
    client: Redis = Redis.from_url(test_redis_url)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture
async def test_redis_settings(
    test_redis_url: str,
    test_redis: Redis,
) -> AsyncGenerator[RedisSettings, None]:
    """Yield ARQ settings for the worker's clean real Redis database."""
    del test_redis
    parsed = urlsplit(test_redis_url)
    if parsed.hostname is None or parsed.port is None:
        message = f"Invalid test Redis URL: {test_redis_url}"
        raise ValueError(message)
    database = int(parsed.path.removeprefix("/") or "0")
    yield RedisSettings(
        host=parsed.hostname,
        port=parsed.port,
        database=database,
    )


@pytest_asyncio.fixture(scope="session")
async def test_engine(
    test_database_url: str,
) -> AsyncGenerator[AsyncEngine, None]:
    """Create one database engine and schema for the entire test session."""
    engine = create_async_engine(
        url=test_database_url,
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
    app.dependency_overrides[rate_limit.enforce_email_action_rate_limit] = (
        override_rate_limit
    )
    app.dependency_overrides[quota.enforce_execution_quota] = override_quota

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
