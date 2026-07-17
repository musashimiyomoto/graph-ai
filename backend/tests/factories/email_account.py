"""Email account model factory."""

from factory.declarations import LazyAttribute

from db.models import EmailAccount
from tests.factories.base import AsyncSQLAlchemyModelFactory, fake
from utils.encryption import encrypt


class EmailAccountFactory(AsyncSQLAlchemyModelFactory):
    """Factory for creating EmailAccount instances."""

    class Meta:
        """Factory meta configuration."""

        model = EmailAccount

    user_id = None
    name = LazyAttribute(lambda _obj: f"email-{fake.word()}")
    email_address = LazyAttribute(lambda _obj: fake.email())
    username = LazyAttribute(lambda obj: obj.email_address)
    password = LazyAttribute(lambda _obj: encrypt(fake.password()))
    imap_host = "imap.example.com"
    imap_port = 993
    imap_use_ssl = True
    smtp_host = "smtp.example.com"
    smtp_port = 587
    smtp_use_tls = True
    smtp_use_ssl = False
    last_uid = 0
    enabled = True
