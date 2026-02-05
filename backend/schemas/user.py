"""User-related API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Shared user fields."""

    email: EmailStr = Field(default=..., description="Email of the user")


class UserCreate(UserBase):
    """Payload for creating a user."""

    password: str = Field(default=..., description="Password of the user")


class UserResponse(UserBase):
    """User response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=..., description="ID of the user", gt=0)

    created_at: datetime = Field(default=..., description="Created at")
    updated_at: datetime = Field(default=..., description="Updated at")
