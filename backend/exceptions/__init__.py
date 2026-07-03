"""Custom exception types for the API."""

from exceptions.auth import AuthCredentialsError
from exceptions.base import BaseError
from exceptions.edge import (
    EdgeNodeMismatchError,
    EdgeNotFoundError,
    EdgePortMismatchError,
)
from exceptions.execution import (
    ExecutionGraphValidationError,
    ExecutionInputValidationError,
    ExecutionNotFoundError,
    NodeExecutionTimeoutError,
)
from exceptions.llm_provider import (
    LLMProviderConfigError,
    LLMProviderConnectionError,
    LLMProviderNotFoundError,
    UnsupportedLLMProviderError,
)
from exceptions.network import BlockedURLError
from exceptions.node import (
    HTTPRequestError,
    NodeDataValidationError,
    NodeNotFoundError,
    WebSearchConnectionError,
)
from exceptions.user import UserAlreadyExistsError, UserNotFoundError
from exceptions.workflow import WorkflowNotFoundError

__all__ = [
    "AuthCredentialsError",
    "BaseError",
    "BlockedURLError",
    "EdgeNodeMismatchError",
    "EdgeNotFoundError",
    "EdgePortMismatchError",
    "ExecutionGraphValidationError",
    "ExecutionInputValidationError",
    "ExecutionNotFoundError",
    "HTTPRequestError",
    "LLMProviderConfigError",
    "LLMProviderConnectionError",
    "LLMProviderNotFoundError",
    "NodeDataValidationError",
    "NodeExecutionTimeoutError",
    "NodeNotFoundError",
    "UnsupportedLLMProviderError",
    "UserAlreadyExistsError",
    "UserNotFoundError",
    "WebSearchConnectionError",
    "WorkflowNotFoundError",
]
