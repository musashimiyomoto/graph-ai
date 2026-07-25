"""Email account use case implementation."""

from sqlalchemy.ext.asyncio import AsyncSession

from credentials import create_profile_connection, update_profile_connection
from db.repositories import ConnectionRepository, EmailAccountRepository
from exceptions import EmailAccountConfigError, EmailAccountNotFoundError
from schemas import EmailAccountCreate, EmailAccountResponse, EmailAccountUpdate
from usecases.audit import AuditEvent, AuditUsecase


class EmailAccountUsecase:
    """Email account business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._repository = EmailAccountRepository()
        self._audit_usecase = AuditUsecase()

    async def create_email_account(
        self, session: AsyncSession, user_id: int, data: EmailAccountCreate
    ) -> EmailAccountResponse:
        """Create an email account with an encrypted password."""
        values = data.model_dump()
        password = values.pop("password")
        connection = await create_profile_connection(
            session=session,
            user_id=user_id,
            name=data.name,
            provider="email",
            secret=password,
        )
        values.update(user_id=user_id, connection_id=connection.id)
        account = await self._repository.create(session=session, data=values)
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="email_account.create",
                entity_type="email_account",
                entity_id=account.id,
                metadata={"name": account.name},
            ),
        )
        await session.commit()
        return EmailAccountResponse.model_validate(account)

    async def get_email_accounts(
        self, session: AsyncSession, user_id: int
    ) -> list[EmailAccountResponse]:
        """List the current user's email accounts."""
        accounts = await self._repository.get_all(session=session, user_id=user_id)
        return [EmailAccountResponse.model_validate(account) for account in accounts]

    async def get_email_account(
        self, session: AsyncSession, account_id: int, user_id: int
    ) -> EmailAccountResponse:
        """Get one user-owned email account."""
        account = await self._repository.get_by(
            session=session, id=account_id, user_id=user_id
        )
        if account is None:
            raise EmailAccountNotFoundError
        return EmailAccountResponse.model_validate(account)

    async def update_email_account(
        self,
        session: AsyncSession,
        account_id: int,
        user_id: int,
        data: EmailAccountUpdate,
    ) -> EmailAccountResponse:
        """Update one user-owned email account."""
        existing = await self._repository.get_by(
            session=session, id=account_id, user_id=user_id
        )
        if existing is None:
            raise EmailAccountNotFoundError
        values = data.model_dump(exclude_none=True)
        if not values:
            return await self.get_email_account(
                session=session, account_id=account_id, user_id=user_id
            )
        replace_secret = "password" in values
        password = values.pop("password", None)
        await update_profile_connection(
            session=session,
            connection_id=existing.connection_id,
            name=values.get("name"),
            secret=password,
            replace_secret=replace_secret,
        )
        smtp_use_tls = values.get("smtp_use_tls", existing.smtp_use_tls)
        smtp_use_ssl = values.get("smtp_use_ssl", existing.smtp_use_ssl)
        if smtp_use_tls and smtp_use_ssl:
            message = "smtp_use_tls and smtp_use_ssl cannot both be enabled"
            raise EmailAccountConfigError(message=message)
        account = await self._repository.update_by(
            session=session, data=values, id=account_id
        )
        if account is None:
            raise EmailAccountNotFoundError
        await session.commit()
        return EmailAccountResponse.model_validate(account)

    async def delete_email_account(
        self, session: AsyncSession, account_id: int, user_id: int
    ) -> None:
        """Delete one user-owned email account."""
        account = await self._repository.get_by(
            session=session, id=account_id, user_id=user_id
        )
        if account is None:
            raise EmailAccountNotFoundError
        await ConnectionRepository().delete_by(
            session=session, id=account.connection_id, user_id=user_id
        )
        await self._audit_usecase.record(
            session=session,
            event=AuditEvent(
                user_id=user_id,
                action="email_account.delete",
                entity_type="email_account",
                entity_id=account_id,
            ),
        )
        await session.commit()
