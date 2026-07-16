"""Observability (Sentry init) tests."""

import pytest

import observability
from settings import sentry_settings


class TestSentryInit:
    """Tests for Sentry initialization."""

    def test_noop_when_dsn_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no DSN, init_sentry does not call sentry_sdk.init."""
        monkeypatch.setattr(sentry_settings, "dsn", "")

        called = False

        def _fake_init(*args: object, **kwargs: object) -> None:
            """Record that init was invoked."""
            nonlocal called
            del args, kwargs
            called = True

        monkeypatch.setattr(observability.sentry_sdk, "init", _fake_init)

        observability.init_sentry(component="test")

        if called:
            pytest.fail("Sentry must not initialize without a DSN")

    def test_initializes_when_dsn_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With a DSN, init_sentry initializes the SDK and tags the component."""
        monkeypatch.setattr(sentry_settings, "dsn", "https://example@sentry.io/1")

        captured: dict[str, object] = {}

        def _fake_init(*args: object, **kwargs: object) -> None:
            """Capture the init kwargs."""
            del args
            captured.update(kwargs)

        def _fake_set_tag(key: str, value: str) -> None:
            """Capture the component tag."""
            captured[key] = value

        monkeypatch.setattr(observability.sentry_sdk, "init", _fake_init)
        monkeypatch.setattr(observability.sentry_sdk, "set_tag", _fake_set_tag)

        observability.init_sentry(component="worker")

        if captured.get("dsn") != "https://example@sentry.io/1":
            pytest.fail("Sentry should initialize with the configured DSN")
        if captured.get("component") != "worker":
            pytest.fail("Sentry should tag the component")
