"""Schemas for LLM provider API payloads."""

from pydantic import BaseModel, ConfigDict, Field

from enums import LLMProviderType


class LLMProviderCreate(BaseModel):
    """Payload for creating an LLM provider."""

    name: str = Field(default=..., description="Provider name")
    type: LLMProviderType = Field(default=..., description="Provider type")
    api_key: str | None = Field(default=None, description="Encrypted API key")
    config: dict = Field(default_factory=dict, description="Provider configuration")
    base_url: str | None = Field(default=None, description="Custom base URL")
    is_default: bool = Field(default=False, description="Is default provider")


class LLMProviderUpdate(BaseModel):
    """Payload for updating an LLM provider."""

    name: str | None = Field(default=None, description="Provider name")
    type: LLMProviderType | None = Field(default=None, description="Provider type")
    api_key: str | None = Field(default=None, description="Encrypted API key")
    config: dict | None = Field(default=None, description="Provider configuration")
    base_url: str | None = Field(default=None, description="Custom base URL")
    is_default: bool | None = Field(default=None, description="Is default provider")


class LLMProviderResponse(BaseModel):
    """Response model for LLM providers."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="Provider ID", gt=0)
    user_id: int = Field(default=..., description="Owner user ID", gt=0)
    name: str = Field(default=..., description="Provider name")
    type: LLMProviderType = Field(default=..., description="Provider type")
    base_url: str | None = Field(default=None, description="Custom base URL")
    is_default: bool = Field(default=..., description="Is default provider")
    config: dict = Field(default=..., description="Provider configuration")


class LLMProviderModelResponse(BaseModel):
    """Response model for an LLM provider model."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(default=..., description="Model name")


class ChatMessage(BaseModel):
    """Chat message payload."""

    role: str = Field(default=..., description="Message role")
    content: str = Field(default=..., description="Message content")


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
