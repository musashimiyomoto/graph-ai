"""Base repository abstraction for SQLAlchemy models."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import BaseWithID


class BaseRepository[Model: BaseWithID]:
    """Generic repository providing CRUD operations."""

    def __init__(self, model: type[Model]) -> None:
        """Initialize the repository with a model class."""
        self.model = model

    async def create(self, session: AsyncSession, data: dict[str, Any]) -> Model:
        """Create a new model instance.

        Args:
            session: The async session.
            data: The data to create the model instance.

        Returns:
            The created model instance.

        """
        instance = self.model(**data)

        session.add(instance)
        await session.commit()
        await session.refresh(instance)

        return instance

    async def create_many(
        self, session: AsyncSession, data: list[dict[str, Any]]
    ) -> list[Model]:
        """Create multiple model instances.

        Args:
            session: The async session.
            data: The list of data to create model instances.

        Returns:
            The list of created model instances.

        """
        instances = [self.model(**data) for data in data]
        session.add_all(instances)
        await session.commit()

        for instance in instances:
            await session.refresh(instance)

        return instances

    async def get_all(
        self,
        session: AsyncSession,
        limit: int | None = None,
        offset: int | None = None,
        *,
        descending: bool = False,
        **filters: object,
    ) -> list[Model]:
        """Get model instances ordered deterministically by primary key.

        Args:
            session: The async session.
            limit: Maximum rows to return (None = no limit).
            offset: Rows to skip before returning results.
            descending: Order by id descending instead of ascending.
            **filters: The equality filters to apply to the query.

        Returns:
            The list of model instances.

        """
        order = self.model.id.desc() if descending else self.model.id.asc()
        statement = select(self.model).filter_by(**filters).order_by(order)
        if offset is not None:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)

        result = await session.execute(statement=statement)
        return list(result.scalars().all())

    async def get_by(self, session: AsyncSession, **filters: object) -> Model | None:
        """Get a model instance by filters.

        Args:
            session: The async session.
            **filters: The filters to apply to the query.

        Returns:
            The model instance.

        """
        result = await session.execute(
            statement=select(self.model).filter_by(**filters)
        )
        return result.scalar_one_or_none()

    async def update_by(
        self, session: AsyncSession, data: dict[str, Any], **filters: object
    ) -> Model | None:
        """Update a model instance by filters.

        Args:
            session: The async session.
            data: The data to update the model instance.
            **filters: The filters to apply to the query.

        Returns:
            The updated model instance.

        """
        instance = await self.get_by(session=session, **filters)

        if instance:
            for key, value in data.items():
                setattr(instance, key, value)

            await session.commit()
            await session.refresh(instance)

        return instance

    async def delete_by(self, session: AsyncSession, **filters: object) -> bool:
        """Delete a model instance by filters.

        Args:
            session: The async session.
            **filters: The filters to apply to the query.

        Returns:
            True if the model instance was deleted, False otherwise.

        """
        instance = await self.get_by(session=session, **filters)

        if instance:
            await session.delete(instance)
            await session.commit()

            return True

        return False

    async def delete_all(self, session: AsyncSession, **filters: object) -> bool:
        """Delete all model instances by filters.

        Args:
            session: The async session.
            **filters: The filters to apply to the query.

        Returns:
            True if the model instances were deleted, False otherwise.

        """
        result = await session.execute(
            statement=select(self.model).filter_by(**filters)
        )
        for instance in result.scalars().all():
            await session.delete(instance)

        await session.commit()

        return True

    async def get_count(self, session: AsyncSession, **filters: object) -> int:
        """Get the count of model instances by filters.

        Args:
            session: The async session.
            **filters: The filters to apply to the query.

        Returns:
            The count of model instances.

        """
        result = await session.execute(
            statement=select(func.count()).select_from(self.model).filter_by(**filters)
        )
        return result.scalar() or 0
