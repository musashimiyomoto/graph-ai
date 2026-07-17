"""Email account dependency providers."""

from usecases import EmailAccountUsecase


def get_email_account_usecase() -> EmailAccountUsecase:
    """Build an email account usecase."""
    return EmailAccountUsecase()
