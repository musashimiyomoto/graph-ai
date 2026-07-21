"""Translate node handler tests."""

from typing import TYPE_CHECKING, ClassVar, Self, cast

import pytest

from exceptions import ExecutionGraphValidationError, TranslationConnectionError
from nodes import NodeValue
from nodes.base import NodeExecutionContext
from nodes.translate import TranslateNodeHandler

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class _TranslationResponse:
    """Fixed successful response for one free translation service."""

    status_code = 200

    def __init__(self, payload: object) -> None:
        """Store JSON returned by the fake endpoint."""
        self._payload = payload

    def raise_for_status(self) -> None:
        """Keep the successful status."""

    def json(self) -> object:
        """Return the configured JSON payload."""
        return self._payload


class _TranslationClient:
    """Async client stub capturing Google and MyMemory requests."""

    calls: ClassVar[list[tuple[str, dict[str, str]]]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Accept normal httpx client options."""
        del args, kwargs

    async def __aenter__(self) -> Self:
        """Enter the context manager."""
        return self

    async def __aexit__(self, *args: object) -> bool:
        """Exit the context manager."""
        del args
        return False

    async def get(self, url: str, *, params: dict[str, str]) -> _TranslationResponse:
        """Capture request parameters and return a service-specific body."""
        self.calls.append((url, params))
        if "googleapis" in url:
            return _TranslationResponse([[["Hola ", "Hello "], ["mundo", "world"]]])
        return _TranslationResponse(
            {"responseData": {"translatedText": "Bonjour &amp; bienvenue"}}
        )


def _context(
    *, service: str, target_language: str, text: str = "Hello world"
) -> NodeExecutionContext:
    """Build a minimal Translate execution context."""
    return NodeExecutionContext(
        session=cast("AsyncSession", None),
        workflow_owner_id=1,
        node_data={"service": service, "target_language": target_language},
        parent_values=[NodeValue.text(text)],
        input_value=NodeValue.text(text),
    )


class TestTranslateNodeHandler:
    """Tests for free external translation services."""

    @pytest.mark.asyncio
    async def test_google_translates_without_llm_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Google receives auto-detect and target language parameters."""
        _TranslationClient.calls = []
        monkeypatch.setattr("nodes.translate.httpx.AsyncClient", _TranslationClient)

        result = await TranslateNodeHandler().execute(
            _context(service="google", target_language="Spanish")
        )

        if result.output.require_text() != "Hola mundo":
            pytest.fail("Google response segments were not joined")
        _, params = _TranslationClient.calls[0]
        if params.get("sl") != "auto" or params.get("tl") != "es":
            pytest.fail("Google language parameters are wrong")
        if "llm_provider_id" in params:
            pytest.fail("Translate must not use an LLM provider")

    @pytest.mark.asyncio
    async def test_mymemory_translates_and_decodes_entities(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MyMemory receives an autodetect language pair and decoded output."""
        _TranslationClient.calls = []
        monkeypatch.setattr("nodes.translate.httpx.AsyncClient", _TranslationClient)

        result = await TranslateNodeHandler().execute(
            _context(service="mymemory", target_language="French")
        )

        if result.output.require_text() != "Bonjour & bienvenue":
            pytest.fail("MyMemory response was not decoded")
        _, params = _TranslationClient.calls[0]
        if params.get("langpair") != "Autodetect|fr":
            pytest.fail("MyMemory language pair is wrong")

    @pytest.mark.asyncio
    async def test_rejects_unknown_service(self) -> None:
        """Only fixed external endpoints may be selected."""
        with pytest.raises(ExecutionGraphValidationError):
            await TranslateNodeHandler().execute(
                _context(service="custom", target_language="English")
            )

    @pytest.mark.asyncio
    async def test_rejects_mymemory_input_over_free_limit(self) -> None:
        """MyMemory's anonymous 500-byte request cap is checked locally."""
        with pytest.raises(ExecutionGraphValidationError):
            await TranslateNodeHandler().execute(
                _context(
                    service="mymemory",
                    target_language="English",
                    text="x" * 501,
                )
            )

    @pytest.mark.asyncio
    async def test_invalid_provider_payload_is_retryable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Malformed external responses become a retryable domain error."""

        class _InvalidClient(_TranslationClient):
            async def get(
                self, url: str, *, params: dict[str, str]
            ) -> _TranslationResponse:
                del url, params
                return _TranslationResponse({"unexpected": True})

        monkeypatch.setattr("nodes.translate.httpx.AsyncClient", _InvalidClient)
        with pytest.raises(TranslationConnectionError) as exc_info:
            await TranslateNodeHandler().execute(
                _context(service="google", target_language="English")
            )
        if not exc_info.value.retryable:
            pytest.fail("Translation service failures should be retried")
