"""Password hashing utilities."""

import bcrypt


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: The plain-text password.

    Returns:
        The bcrypt hash.

    """
    return bcrypt.hashpw(password=password.encode(), salt=bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash.

    Args:
        password: The plain-text password.
        hashed: The bcrypt hash.

    Returns:
        Whether the password matches the hash.

    """
    return bcrypt.checkpw(password=password.encode(), hashed_password=hashed.encode())
