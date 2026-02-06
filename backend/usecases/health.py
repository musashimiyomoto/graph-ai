"""Usecase logic for health checks."""

import asyncio
from http import HTTPStatus

import httpx
import redis.asyncio
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from sessions import async_session
from settings import chroma_settings, prefect_settings
from utils.redis import redis_client


class HealthUsecase:
    """Usecase operations for health checks."""

    async def check_postgres(self) -> bool:
        """Check postgres connectivity.

        Returns:
            True if postgres is healthy, False otherwise.

        """
        try:
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except SQLAlchemyError:
            return False

    async def check_chroma(self) -> bool:
        """Check Chroma connectivity.

        Returns:
            True if chroma is healthy, False otherwise.

        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{chroma_settings.url}/api/v2/heartbeat",
                    timeout=5.0,
                )
                return response.status_code == HTTPStatus.OK
        except httpx.HTTPError:
            return False

    async def check_prefect(self) -> bool:
        """Check Prefect server connectivity.

        Returns:
            True if prefect is healthy, False otherwise.

        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{prefect_settings.url}/api/health",
                    timeout=5.0,
                )
                return response.status_code == HTTPStatus.OK
        except httpx.HTTPError:
            return False

    async def check_redis(self) -> bool:
        """Check Redis connectivity.

        Returns:
            True if Redis is healthy, False otherwise.

        """
        try:
            return await redis_client.ping()
        except redis.RedisError:
            return False

    async def health(self) -> dict[str, bool]:
        """Check all services concurrently.

        Returns:
            Dictionary of service names and their health status.

        """
        tasks = [
            ("postgres", self.check_postgres()),
            ("redis", self.check_redis()),
            ("chroma", self.check_chroma()),
            ("prefect", self.check_prefect()),
        ]

        results = await asyncio.gather(
            *[task[1] for task in tasks], return_exceptions=True
        )

        service_checks = {}
        for service_name, result in zip(
            [task[0] for task in tasks], results, strict=False
        ):
            if isinstance(result, Exception):
                service_checks[service_name] = False
            else:
                service_checks[service_name] = result

        return service_checks
