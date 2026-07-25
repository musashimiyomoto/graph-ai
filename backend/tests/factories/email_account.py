"""Email account model factory."""

from factory.declarations import LazyAttribute
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import EmailAccount
from tests.factories.base import AsyncSQLAlchemyModelFactory, ModelT, fake
from tests.factories.connection import ConnectionFactory


class EmailAccountFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating EmailAccount instances."""

    class Meta:
        """Factory meta configuration."""

        model = EmailAccount

    user_id = None
    name = LazyAttribute(lambda _obj: f"email-{fake.word()}")
    email_address = LazyAttribute(lambda _obj: fake.email())
    username = LazyAttribute(lambda obj: obj.email_address)
    imap_host = "imap.example.com"
    imap_port = 993
    imap_use_ssl = True
    smtp_host = "smtp.example.com"
    smtp_port = 587
    smtp_use_tls = True
    smtp_use_ssl = False
    last_uid = 0
    enabled = True

    @classmethod
    async def create_async(cls, session: AsyncSession, **kwargs: object) -> ModelT:
        """Create the unified credential row before the email profile."""
        connection = await ConnectionFactory.create_async(
            session=session,
            user_id=kwargs.get("user_id"),
            provider="email",
        )
        kwargs["connection_id"] = connection.id
        return await super().create_async(session=session, **kwargs)
