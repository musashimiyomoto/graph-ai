"""Shared environment constants for secure-by-default settings."""

# Environments where insecure default secrets are tolerated. Any other
# environment (production, prod, staging, ...) must supply real keys.
INSECURE_KEY_ENVIRONMENTS = frozenset({"local", "test"})
