"""Schemas for saved MCP servers and discovered tools."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MCPServerCreate(BaseModel):
    """Payload for registering a remote Streamable HTTP MCP server."""

    name: str = Field(default=..., min_length=1, max_length=128)
    url: str = Field(default=..., min_length=1, max_length=2048)
    headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """Require an absolute HTTP(S) URL."""
        if not value.startswith(("http://", "https://")):
            message = "MCP server URL must start with http:// or https://"
            raise ValueError(message)
        return value


class MCPServerResponse(BaseModel):
    """Public MCP server metadata without secret headers."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., gt=0)
    user_id: int = Field(default=..., gt=0)
    name: str
    url: str
    has_headers: bool = False


class MCPToolResponse(BaseModel):
    """Tool metadata discovered from an MCP server."""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
