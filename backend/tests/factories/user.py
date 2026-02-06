"""User model factory."""

from factory.declarations import LazyAttribute
from factory.helpers import post_generation

from models.user import User
from tests.factories.base import AsyncSQLAlchemyModelFactory, fake


class UserFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating User instances."""

    class Meta:
        """Factory meta configuration."""

        model = User

    email = LazyAttribute(lambda _obj: fake.email())

    hashed_password = LazyAttribute(lambda _obj: fake.password())

    @post_generation
    def set_hashed_password(
        self, _create: object, extracted: str | None, **_kwargs: object
    ) -> None:
        """Override hashed_password if a plain password is provided.

        Args:
            _create: Whether the instance is being created.
            extracted: The extracted password value.
            **_kwargs: Additional keyword arguments.

        """
        if extracted:
            self.hashed_password = f"hashed_{extracted}"
