"""Custom exception types for the API."""

from exceptions.auth import AuthCredentialsError
from exceptions.base import BaseError
from exceptions.edge import EdgeNodeMismatchError, EdgeNotFoundError
from exceptions.execution import (
    ExecutionGraphValidationError,
    ExecutionInputValidationError,
    ExecutionNotFoundError,
)
from exceptions.llm_provider import (
    LLMProviderConfigError,
    LLMProviderConnectionError,
    LLMProviderNotFoundError,
    UnsupportedLLMProviderError,
)
from exceptions.node import (
    NodeDataValidationError,
    NodeNotFoundError,
    WebSearchConnectionError,
)
from exceptions.user import UserAlreadyExistsError, UserNotFoundError
from exceptions.workflow import WorkflowNotFoundError

__all__ = [
    "AuthCredentialsError",
    "BaseError",
    "EdgeNodeMismatchError",
    "EdgeNotFoundError",
    "ExecutionGraphValidationError",
    "ExecutionInputValidationError",
    "ExecutionNotFoundError",
    "LLMProviderConfigError",
    "LLMProviderConnectionError",
    "LLMProviderNotFoundError",
    "NodeDataValidationError",
    "NodeNotFoundError",
    "UnsupportedLLMProviderError",
    "UserAlreadyExistsError",
    "UserNotFoundError",
    "WebSearchConnectionError",
    "WorkflowNotFoundError",
]
