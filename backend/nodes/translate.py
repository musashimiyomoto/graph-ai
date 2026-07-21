"""Translate node backed by free external translation services."""

from html import unescape
from typing import cast

import httpx

from constants import DEFAULT_TIMEOUT
from enums import NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError, TranslationConnectionError
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from schemas import NodeFieldSpec, NodeFieldUI, NodeFieldWidget, NodeGraphSpec

_GOOGLE = "google"
_MYMEMORY = "mymemory"
_SERVICES = (_GOOGLE, _MYMEMORY)
_GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"
_MYMEMORY_URL = "https://api.mymemory.translated.net/get"
_GOOGLE_MAX_CHARS = 5_000
_MYMEMORY_MAX_BYTES = 500
_USER_AGENT = "GraphAI/1.0"

TARGET_LANGUAGES = {
    "Arabic": "ar",
    "Chinese (Simplified)": "zh-CN",
    "Chinese (Traditional)": "zh-TW",
    "Dutch": "nl",
    "English": "en",
    "French": "fr",
    "German": "de",
    "Hindi": "hi",
    "Indonesian": "id",
    "Italian": "it",
    "Japanese": "ja",
    "Korean": "ko",
    "Polish": "pl",
    "Portuguese": "pt",
    "Russian": "ru",
    "Spanish": "es",
    "Turkish": "tr",
    "Ukrainian": "uk",
}


class TranslateNodeHandler:
    """Translate upstream text without consuming an LLM provider."""

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Translate all upstream text with the selected free service.

        Args:
            context: Node execution context.

        Returns:
            Translated text.

        Raises:
            ExecutionGraphValidationError: If configuration or input is invalid.
            TranslationConnectionError: If the service call or response fails.

        """
        service = context.node_data.get("service")
        if not isinstance(service, str) or service not in _SERVICES:
            message = "Translate node requires a supported service"
            raise ExecutionGraphValidationError(message=message)

        target_language = context.node_data.get("target_language")
        if (
            not isinstance(target_language, str)
            or target_language not in TARGET_LANGUAGES
        ):
            message = "Translate node requires a supported target_language"
            raise ExecutionGraphValidationError(message=message)

        text = context.joined_parent_text().strip() or context.input_text.strip()
        if not text:
            message = "Translate node input is empty"
            raise ExecutionGraphValidationError(message=message)

        language_code = TARGET_LANGUAGES[target_language]
        self._validate_input_size(text=text, service=service)
        translated = await self._translate(
            text=text,
            target_language=language_code,
            service=service,
        )
        return NodeExecutionResult.text(translated)

    @staticmethod
    def _validate_input_size(text: str, service: str) -> None:
        """Reject input above the selected free endpoint's request limit."""
        if service == _GOOGLE and len(text) > _GOOGLE_MAX_CHARS:
            message = (
                f"Google Translate input is limited to {_GOOGLE_MAX_CHARS} characters"
            )
            raise ExecutionGraphValidationError(message=message)
        if service == _MYMEMORY and len(text.encode()) > _MYMEMORY_MAX_BYTES:
            message = f"MyMemory input is limited to {_MYMEMORY_MAX_BYTES} UTF-8 bytes"
            raise ExecutionGraphValidationError(message=message)

    async def _translate(
        self,
        *,
        text: str,
        target_language: str,
        service: str,
    ) -> str:
        """Call one fixed translation endpoint and parse its response."""
        if service == _GOOGLE:
            url = _GOOGLE_URL
            params = {
                "client": "gtx",
                "sl": "auto",
                "tl": target_language,
                "dt": "t",
                "q": text,
            }
        else:
            url = _MYMEMORY_URL
            params = {
                "q": text,
                "langpair": f"Autodetect|{target_language}",
            }

        try:
            async with httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload: object = response.json()
        except httpx.TimeoutException as exc:
            message = "Translation service request timed out"
            raise TranslationConnectionError(message=message) from exc
        except httpx.HTTPStatusError as exc:
            message = f"Translation service returned {exc.response.status_code}"
            raise TranslationConnectionError(message=message) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise TranslationConnectionError from exc

        if service == _GOOGLE:
            return self._parse_google_response(payload)
        return self._parse_mymemory_response(payload)

    @staticmethod
    def _parse_google_response(payload: object) -> str:
        """Extract translated segments from Google's free web endpoint shape."""
        if not isinstance(payload, list) or not payload:
            raise TranslationConnectionError(message="Google returned invalid JSON")
        segments = payload[0]
        if not isinstance(segments, list):
            raise TranslationConnectionError(message="Google returned invalid JSON")

        translated_parts = [
            segment[0]
            for segment in segments
            if isinstance(segment, list) and segment and isinstance(segment[0], str)
        ]
        if not translated_parts:
            raise TranslationConnectionError(message="Google returned no translation")
        return "".join(translated_parts)

    @staticmethod
    def _parse_mymemory_response(payload: object) -> str:
        """Extract translated text from MyMemory's public API response."""
        if not isinstance(payload, dict):
            raise TranslationConnectionError(message="MyMemory returned invalid JSON")
        typed_payload = cast("dict[str, object]", payload)
        response_data = typed_payload.get("responseData")
        if not isinstance(response_data, dict):
            raise TranslationConnectionError(message="MyMemory returned invalid JSON")
        typed_response = cast("dict[str, object]", response_data)
        translated = typed_response.get("translatedText")
        if not isinstance(translated, str) or not translated:
            raise TranslationConnectionError(message="MyMemory returned no translation")
        return unescape(translated)


def _build_handler(deps: NodeHandlerDeps) -> TranslateNodeHandler:
    """Build a Translate node handler."""
    del deps
    return TranslateNodeHandler()


DEFINITION = NodeDefinition(
    type=NodeType.TRANSLATE,
    label="Translate",
    icon_key="translate",
    graph=NodeGraphSpec(
        has_input=True,
        has_output=True,
        input_port=PortType.TEXT,
        output_port=PortType.TEXT,
    ),
    fields=(
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Translate label",
            ),
            default="Translate",
        ),
        NodeFieldSpec(
            name="service",
            required=True,
            validators={ValidatorType.SELECT.value: _SERVICES},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SELECT,
                label="Translation service",
                help=(
                    "Sends text to the selected third party. Google uses an "
                    "unofficial free web endpoint; MyMemory uses its public "
                    "anonymous API with stricter request and daily limits. "
                    "Neither requires an API key."
                ),
            ),
            default=_GOOGLE,
        ),
        NodeFieldSpec(
            name="target_language",
            required=True,
            validators={ValidatorType.SELECT.value: tuple(TARGET_LANGUAGES)},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.SELECT,
                label="Target language",
                help="The source language is detected automatically.",
            ),
            default="English",
        ),
    ),
    build_handler=_build_handler,
)
