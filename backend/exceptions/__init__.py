"""Custom exception types for the API."""

from exceptions.auth import AuthCredentialsError
from exceptions.base import BaseError
from exceptions.edge import (
    EdgeAlreadyExistsError,
    EdgeHandleMismatchError,
    EdgeNodeMismatchError,
    EdgeNotFoundError,
    EdgePortMismatchError,
)
from exceptions.email import (
    EmailAccountConfigError,
    EmailAccountNotFoundError,
    EmailConnectionError,
)
from exceptions.execution import (
    ExecutionGraphValidationError,
    ExecutionInputValidationError,
    ExecutionNotFoundError,
    NodeExecutionTimeoutError,
)
from exceptions.llm_provider import (
    LLMProviderAlreadyExistsError,
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
from exceptions.quota import QuotaExceededError
from exceptions.rag import (
    DocumentTooLargeError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
    VectorCollectionNotFoundError,
    VectorDocumentNotFoundError,
)
from exceptions.rate_limit import RateLimitExceededError
from exceptions.telegram import TelegramAPIError, TelegramBotNotFoundError
from exceptions.user import UserAlreadyExistsError, UserNotFoundError
from exceptions.web_chat import WebChatNotFoundError
from exceptions.webhook import WebhookConnectionError, WebhookNotFoundError
from exceptions.workflow import (
    WorkflowNotFoundError,
    WorkflowTemplateNotFoundError,
    WorkflowVersionNotFoundError,
)

__all__ = [
    "AuthCredentialsError",
    "BaseError",
    "BlockedURLError",
    "DocumentTooLargeError",
    "EdgeAlreadyExistsError",
    "EdgeHandleMismatchError",
    "EdgeNodeMismatchError",
    "EdgeNotFoundError",
    "EdgePortMismatchError",
    "EmailAccountConfigError",
    "EmailAccountNotFoundError",
    "EmailConnectionError",
    "EmptyDocumentError",
    "ExecutionGraphValidationError",
    "ExecutionInputValidationError",
    "ExecutionNotFoundError",
    "HTTPRequestError",
    "LLMProviderAlreadyExistsError",
    "LLMProviderConfigError",
    "LLMProviderConnectionError",
    "LLMProviderNotFoundError",
    "NodeDataValidationError",
    "NodeExecutionTimeoutError",
    "NodeNotFoundError",
    "QuotaExceededError",
    "RateLimitExceededError",
    "TelegramAPIError",
    "TelegramBotNotFoundError",
    "UnsupportedDocumentTypeError",
    "UnsupportedLLMProviderError",
    "UserAlreadyExistsError",
    "UserNotFoundError",
    "VectorCollectionNotFoundError",
    "VectorDocumentNotFoundError",
    "WebChatNotFoundError",
    "WebSearchConnectionError",
    "WebhookConnectionError",
    "WebhookNotFoundError",
    "WorkflowNotFoundError",
    "WorkflowTemplateNotFoundError",
    "WorkflowVersionNotFoundError",
]
