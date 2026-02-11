"""Schemas for LLM provider API payloads."""

from pydantic import BaseModel, ConfigDict, Field

from enums import LLMProviderType


class LLMModel(BaseModel):
    """Model metadata returned by an LLM provider."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(default=..., description="Model name")


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


class ChatRequest(BaseModel):
    """Chat request payload."""

    model_config = ConfigDict(frozen=True)

    model: str = Field(default=..., description="Model name")
    messages: list[ChatMessage] = Field(
        default_factory=list,
        description="Messages for provider request",
    )


class LLMProviderCreate(BaseModel):
    """Payload for creating an LLM provider."""

    name: str = Field(default=..., description="Provider name")
    type: LLMProviderType = Field(default=..., description="Provider type")
    config: dict = Field(default_factory=dict, description="Provider configuration")
    base_url: str | None = Field(default=None, description="Custom base URL")


class LLMProviderUpdate(BaseModel):
    """Payload for updating an LLM provider."""

    name: str | None = Field(default=None, description="Provider name")
    type: LLMProviderType | None = Field(default=None, description="Provider type")
    config: dict | None = Field(default=None, description="Provider configuration")
    base_url: str | None = Field(default=None, description="Custom base URL")


class LLMProviderResponse(BaseModel):
    """Response model for LLM providers."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Provider ID", gt=0)
    user_id: int = Field(default=..., description="Owner user ID", gt=0)
    name: str = Field(default=..., description="Provider name")
    type: LLMProviderType = Field(default=..., description="Provider type")
    base_url: str | None = Field(default=None, description="Custom base URL")
    config: dict = Field(default=..., description="Provider configuration")


class LLMProviderModelResponse(BaseModel):
    """Response model for an LLM provider model."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(default=..., description="Model name")


class LLMProviderChatRequest(BaseModel):
    """Request payload for LLM chat."""

    model: str = Field(default=..., description="Model name")
    messages: list[ChatMessage] = Field(
        default_factory=list, description="Chat messages"
    )
    options: dict | None = Field(default=None, description="Provider options")
    stream: bool = Field(default=False, description="Enable streaming responses")


class LLMProviderChatResponse(BaseModel):
    """Response payload for LLM chat."""

    model_config = ConfigDict(extra="allow")

    model: str = Field(default=..., description="Model name")
    message: ChatMessage = Field(default=..., description="Response message")
    done: bool = Field(default=..., description="Whether the response is complete")
