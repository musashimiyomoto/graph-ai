"""Schemas for LLM provider API payloads."""

import json

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from enums import LLMProviderType

# Bounds the serialized size of the free-form `config` dict, not its shape.
_MAX_CONFIG_JSON_LENGTH = 10_000


def _validate_config_size(config: dict) -> dict:
    """Reject a config dict whose JSON serialization is too large."""
    if len(json.dumps(config)) > _MAX_CONFIG_JSON_LENGTH:
        message = (
            f"config must serialize to at most {_MAX_CONFIG_JSON_LENGTH} characters"
        )
        raise ValueError(message)
    return config


class ChatMessage(BaseModel):
    """Chat message payload."""

    model_config = ConfigDict(frozen=True)

    role: str = Field(default=..., description="Message role")
    content: str = Field(default=..., description="Message content")


class ChatResponse(BaseModel):
    """Chat response payload."""

    model_config = ConfigDict(frozen=True)

    model: str = Field(default=..., description="Model name")
    message: ChatMessage = Field(default=..., description="Response message")
    done: bool = Field(default=..., description="Completion flag")
    raw: dict[str, object] = Field(default_factory=dict, description="Raw payload")


class GenerationParams(BaseModel):
    """Optional generation parameters for an LLM chat request."""

    model_config = ConfigDict(frozen=True)

    temperature: float | None = Field(
        default=None, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_tokens: int | None = Field(
        default=None, gt=0, description="Maximum tokens to generate"
    )
    top_p: float | None = Field(
        default=None, gt=0.0, le=1.0, description="Nucleus sampling probability"
    )


class LLMProviderCreate(BaseModel):
    """Payload for creating an LLM provider."""

    name: str = Field(
        default=..., description="Provider name", min_length=1, max_length=200
    )
    type: LLMProviderType = Field(default=..., description="Provider type")
    config: dict = Field(default_factory=dict, description="Provider configuration")
    api_key: str | None = Field(
        default=None, description="API key for cloud providers (write-only)"
    )
    base_url: AnyHttpUrl = Field(default=..., description="Custom base URL")

    @field_validator("config")
    @classmethod
    def _validate_config_size(cls, config: dict) -> dict:
        """Reject a config dict whose JSON serialization is too large."""
        return _validate_config_size(config)


class LLMProviderUpdate(BaseModel):
    """Payload for updating an LLM provider."""

    name: str | None = Field(
        default=None, description="Provider name", min_length=1, max_length=200
    )
    type: LLMProviderType | None = Field(default=None, description="Provider type")
    config: dict | None = Field(default=None, description="Provider configuration")
    api_key: str | None = Field(
        default=None, description="API key for cloud providers (write-only)"
    )
    base_url: AnyHttpUrl | None = Field(default=None, description="Custom base URL")

    @model_validator(mode="after")
    def validate_base_url(self) -> "LLMProviderUpdate":
        """Reject explicit null for base_url in PATCH payloads."""
        if "base_url" in self.model_fields_set and self.base_url is None:
            raise ValueError
        return self

    @field_validator("config")
    @classmethod
    def _validate_config_size_optional(cls, config: dict | None) -> dict | None:
        """Reject a config dict whose JSON serialization is too large."""
        if config is None:
            return None
        return _validate_config_size(config)


class LLMProviderResponse(BaseModel):
    """Response model for LLM providers."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Provider ID", gt=0)
    user_id: int = Field(default=..., description="Owner user ID", gt=0)
    name: str = Field(default=..., description="Provider name")
    type: LLMProviderType = Field(default=..., description="Provider type")
    base_url: str = Field(default=..., description="Custom base URL")
    config: dict = Field(default=..., description="Provider configuration")


class LLMProviderModelResponse(BaseModel):
    """Response model for an LLM provider model."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(default=..., description="Model name")


class OllamaCatalogTag(BaseModel):
    """One pullable tag of a curated Ollama model."""

    model_config = ConfigDict(frozen=True)

    tag: str = Field(default=..., description="Full pullable name, e.g. llama3.2:1b")
    size_gb: float = Field(default=..., description="Approximate download size in GB")
    params: str = Field(default=..., description="Parameter count, e.g. 3B")


class OllamaCatalogEntry(BaseModel):
    """A curated Ollama model family and its pullable tags."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(default=..., description="Model family name")
    description: str = Field(default=..., description="Short description")
    tags: list[OllamaCatalogTag] = Field(default=..., description="Pullable tags")


class OllamaModelPullRequest(BaseModel):
    """Payload to start pulling an Ollama model."""

    model: str = Field(
        default=..., description="Model name/tag to pull", min_length=1, max_length=200
    )


class OllamaModelPullResponse(BaseModel):
    """Acknowledgement that a model pull has been queued."""

    job_id: str = Field(default=..., description="Background pull job identifier")
    model: str = Field(default=..., description="Model name/tag being pulled")
