"""Custom exception types for the API."""

from exceptions.auth import AuthCredentialsError
from exceptions.base import BaseError
from exceptions.edge import EdgeNodeMismatchError, EdgeNotFoundError
from exceptions.execution import ExecutionNotFoundError
from exceptions.llm_provider import LLMProviderNotFoundError
from exceptions.node import (
    NodeConfigExistsError,
    NodeNotFoundError,
    NodeTypeMismatchError,
)
from exceptions.user import UserAlreadyExistsError, UserNotFoundError
from exceptions.workflow import WorkflowNotFoundError

__all__ = [
    "AuthCredentialsError",
    "BaseError",
    "EdgeNodeMismatchError",
    "EdgeNotFoundError",
    "ExecutionNotFoundError",
    "LLMProviderNotFoundError",
    "NodeConfigExistsError",
    "NodeNotFoundError",
    "NodeTypeMismatchError",
    "UserAlreadyExistsError",
    "UserNotFoundError",
    "WorkflowNotFoundError",
]
