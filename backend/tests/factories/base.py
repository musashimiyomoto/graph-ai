"""Base factory for async SQLAlchemy model creation."""

from typing import TypeVar, cast

from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

fake = Faker("en_US")

ModelT = TypeVar("ModelT")


class AsyncSQLAlchemyModelFactory(SQLAlchemyModelFactory):
    """Factory base that supports async session creation."""

    class Meta:
        """Factory meta configuration."""

        abstract = True
        sqlalchemy_session_persistence = "commit"

    @classmethod
    async def create_async(cls, session: AsyncSession, **kwargs: object) -> ModelT:
        """Build and persist an instance via an async session.

        Args:
            session: The async database session.
            **kwargs: Model field overrides.

        Returns:
            The persisted model instance.

        """
        instance = cls.build(**kwargs)
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return cast("ModelT", instance)
