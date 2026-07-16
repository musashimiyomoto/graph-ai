"""Usage and audit dependency providers."""

from usecases import AuditUsecase, UsageUsecase


def get_usage_usecase() -> UsageUsecase:
    """Return the usage usecase."""
    return UsageUsecase()


def get_audit_usecase() -> AuditUsecase:
    """Return the audit usecase."""
    return AuditUsecase()
