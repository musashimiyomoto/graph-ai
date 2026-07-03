"""Network safety helpers (SSRF protection for outbound requests)."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = ("http", "https")


def _address_reason(ip: str, *, allow_private: bool) -> str | None:
    """Return a block reason for a resolved IP, or None when it is allowed.

    Link-local (incl. cloud metadata 169.254.169.254), multicast, reserved, and
    unspecified addresses are always blocked. Loopback/private ranges are blocked
    only in strict mode (``allow_private=False``); self-hosted providers such as
    Ollama legitimately live on private/loopback hosts, so they use the lenient mode.

    Args:
        ip: Resolved IP address string.
        allow_private: Whether loopback/private ranges are permitted.

    Returns:
        A human-readable reason if the address is blocked, else None.

    """
    address = ipaddress.ip_address(ip)
    if (
        address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        return f"URL resolves to a disallowed address ({ip})"
    if not allow_private and (address.is_loopback or address.is_private):
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
