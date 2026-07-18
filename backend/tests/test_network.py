"""SSRF guard tests for outbound URL validation."""

import pytest

from utils.network import blocked_url_reason


class TestBlockedUrlReason:
    """Tests for the SSRF URL guard.

    IP literals are used so the checks are deterministic and offline (no DNS).
    """

    @pytest.mark.asyncio
    async def test_public_ip_allowed(self) -> None:
        """A public IP is allowed in strict mode."""
        if await blocked_url_reason("https://1.1.1.1") is not None:
            pytest.fail("Public IP should be allowed")

    @pytest.mark.asyncio
    async def test_loopback_blocked_strict(self) -> None:
        """Loopback is blocked in strict mode."""
        if await blocked_url_reason("http://127.0.0.1") is None:
            pytest.fail("Loopback must be blocked in strict mode")

    @pytest.mark.asyncio
    async def test_private_blocked_strict(self) -> None:
        """Private ranges are blocked in strict mode."""
        if await blocked_url_reason("http://10.0.0.5:8080") is None:
            pytest.fail("Private address must be blocked in strict mode")

    @pytest.mark.asyncio
    async def test_loopback_allowed_when_private_permitted(self) -> None:
        """Self-hosted providers may use loopback/private hosts."""
        if await blocked_url_reason("http://127.0.0.1", allow_private=True) is not None:
            pytest.fail("Loopback should be allowed for providers")

    @pytest.mark.asyncio
    async def test_ipv6_loopback_allowed_when_private_permitted(self) -> None:
        """IPv6 localhost is allowed when private hosts are explicitly permitted."""
        if await blocked_url_reason("http://[::1]", allow_private=True) is not None:
            pytest.fail("IPv6 loopback should be allowed for providers")

    @pytest.mark.asyncio
    async def test_metadata_blocked_even_when_private_permitted(self) -> None:
        """Cloud metadata (link-local) is blocked even in lenient mode."""
        reason = await blocked_url_reason(
            "http://169.254.169.254/latest/meta-data", allow_private=True
        )
        if reason is None:
            pytest.fail("Link-local metadata endpoint must always be blocked")

    @pytest.mark.asyncio
    async def test_non_http_scheme_blocked(self) -> None:
        """Non-http(s) schemes are rejected."""
        if await blocked_url_reason("ftp://10.0.0.1") is None:
            pytest.fail("Non-http(s) scheme must be blocked")

    @pytest.mark.asyncio
    async def test_missing_host_blocked(self) -> None:
        """A URL without a host is rejected."""
        if await blocked_url_reason("http://") is None:
            pytest.fail("URL without host must be blocked")
