"""Usecase logic for health checks."""

import asyncio

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from sessions import async_session


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

    async def health(self) -> dict[str, bool]:
        """Check all services concurrently.

        Returns:
            Dictionary of service names and their health status.

        """
        tasks = [("postgres", self.check_postgres())]

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
