"""Base repository abstraction for SQLAlchemy models."""

from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import BaseWithID


class BaseRepository[Model: BaseWithID]:
    """Generic repository providing CRUD operations."""

    def __init__(self, model: type[Model]) -> None:
        """Initialize the repository with a model class."""
        self.model = model

    def _filter_conditions(
        self, filters: dict[str, object]
    ) -> list[ColumnElement[bool]]:
        """Build per-column conditions, treating a list value as membership.

        A plain (non-list) value stays an equality filter, same as the
        `filter_by` this replaces; a `list`/`tuple`/`set` value becomes an
        `IN` filter instead — e.g. filtering executions by several trigger
        sources at once rather than being restricted to exactly one.

        Args:
            filters: Column name to filter value.

        Returns:
            One condition per filter, ANDed together by the caller.

        """
        conditions: list[ColumnElement[bool]] = []
        for key, value in filters.items():
            column = getattr(self.model, key)
            if isinstance(value, list | tuple | set):
                conditions.append(column.in_(value))
            else:
                conditions.append(column == value)
        return conditions

    async def create(self, session: AsyncSession, data: dict[str, Any]) -> Model:
        """Stage a new model instance (flushed, not committed).

        The caller commits — this lets a usecase batch several writes into
        one atomic unit instead of each write being its own transaction.

        Args:
            session: The async session.
            data: The data to create the model instance.

        Returns:
            The created model instance.

        """
        instance = self.model(**data)

        session.add(instance)
        await session.flush()
        await session.refresh(instance)

        return instance

    async def create_many(
        self, session: AsyncSession, data: list[dict[str, Any]]
    ) -> list[Model]:
        """Stage multiple model instances (flushed, not committed).

        The caller commits — see `create`.

        Args:
            session: The async session.
            data: The list of data to create model instances.

        Returns:
            The list of created model instances.

        """
        instances = [self.model(**data) for data in data]
        session.add_all(instances)
        await session.flush()

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
            **filters: Equality filters; a `list`/`tuple`/`set` value filters
                by membership (`IN`) instead of exact match.

        Returns:
            The list of model instances.

        """
        order = self.model.id.desc() if descending else self.model.id.asc()
        statement = (
            select(self.model).where(*self._filter_conditions(filters)).order_by(order)
        )
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
        """Stage an update to a model instance by filters (flushed, not committed).

        The caller commits — see `create`.

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

            await session.flush()
            await session.refresh(instance)

        return instance

    async def delete_by(self, session: AsyncSession, **filters: object) -> bool:
        """Stage deleting a model instance by filters (flushed, not committed).

        The caller commits — see `create`.

        Args:
            session: The async session.
            **filters: The filters to apply to the query.

        Returns:
            True if the model instance was deleted, False otherwise.

        """
        instance = await self.get_by(session=session, **filters)

        if instance:
            await session.delete(instance)
            await session.flush()

            return True

        return False

    async def delete_all(self, session: AsyncSession, **filters: object) -> bool:
        """Stage deleting all model instances by filters (flushed, not committed).

        The caller commits — see `create`.

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

        await session.flush()

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
