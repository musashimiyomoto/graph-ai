"""Schemas for LLM provider API payloads."""

from pydantic import BaseModel, ConfigDict, Field

from enums import LLMProviderType


class LLMProviderCreate(BaseModel):
    """Payload for creating an LLM provider."""

    name: str = Field(default=..., description="Provider name")
    type: LLMProviderType = Field(default=..., description="Provider type")
    api_key: str = Field(default=..., description="Encrypted API key")
    base_url: str | None = Field(default=None, description="Custom base URL")
    is_default: bool = Field(default=False, description="Is default provider")


class LLMProviderUpdate(BaseModel):
    """Payload for updating an LLM provider."""

    name: str | None = Field(default=None, description="Provider name")
    type: LLMProviderType | None = Field(default=None, description="Provider type")
    api_key: str | None = Field(default=None, description="Encrypted API key")
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
