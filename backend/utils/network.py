"""Network safety helpers (SSRF protection for outbound requests)."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = ("http", "https")


def _address_reason(ip: str, *, allow_private: bool) -> str | None:
    """Return a block reason for a resolved IP, or None when it is allowed.

    Link-local (incl. cloud metadata 169.254.169.254), multicast, non-loopback
    reserved, and unspecified addresses are always blocked. Loopback/private ranges
    are blocked only in strict mode (``allow_private=False``); self-hosted providers
    such as Ollama legitimately live on private/loopback hosts, so they use the
    lenient mode.

    Args:
        ip: Resolved IP address string.
        allow_private: Whether loopback/private ranges are permitted.

    Returns:
        A human-readable reason if the address is blocked, else None.

    """
    address = ipaddress.ip_address(ip)
    if address.is_link_local or address.is_multicast or address.is_unspecified:
        return f"URL resolves to a disallowed address ({ip})"
    if address.is_loopback:
        if not allow_private:
            return f"URL resolves to a private or loopback address ({ip})"
        return None
    if address.is_reserved:
        return f"URL resolves to a disallowed address ({ip})"
    if address.is_private and not allow_private:
        return f"URL resolves to a private or loopback address ({ip})"
    return None


async def blocked_url_reason(url: str, *, allow_private: bool = False) -> str | None:
    """Check whether a URL is safe to request server-side (SSRF guard).

    Resolves the host and rejects the request if any resolved address is disallowed.

    Args:
        url: The absolute http(s) URL to check.
        allow_private: Permit loopback/private hosts (for self-hosted providers).

    Returns:
        A human-readable reason if the URL must be blocked, else None.

    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.hostname:
        return "URL must be an absolute http(s) URL with a host"

    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            parsed.port,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror:
        # An unresolvable host cannot be connected to, so there is nothing to
        # protect against; let the real request fail naturally instead.
        return None

    for info in infos:
        ip = str(info[4][0])
        reason = _address_reason(ip, allow_private=allow_private)
        if reason is not None:
            return reason
    return None


async def blocked_host_reason(
    host: str, port: int, *, allow_private: bool = False
) -> str | None:
    """Check a non-HTTP host/port using the same SSRF address policy.

    Args:
        host: DNS name or IP address.
        port: TCP port used for resolution.
        allow_private: Whether private and loopback addresses are permitted.

    Returns:
        A human-readable block reason, or None when the host is allowed.

    """
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, host, port, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror:
        return None
    for info in infos:
        reason = _address_reason(str(info[4][0]), allow_private=allow_private)
        if reason is not None:
            return reason
    return None


async def blocked_postgres_dsn_reason(dsn: str) -> str | None:
    """Validate a PostgreSQL DSN host using the non-HTTP address policy.

    Args:
        dsn: PostgreSQL connection string.

    Returns:
        A human-readable block reason, or None when the host is allowed.

    """
    parsed = urlparse(dsn)
    if parsed.hostname is None:
        return "PostgreSQL DSN must include a host"
    return await blocked_host_reason(
        parsed.hostname, parsed.port or 5432, allow_private=True
    )
