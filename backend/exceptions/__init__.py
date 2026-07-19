"""Custom exception types for the API."""

from exceptions.auth import AuthCredentialsError, AuthSessionNotFoundError
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
    ExecutionApprovalNotPendingError,
    ExecutionGraphValidationError,
    ExecutionInputValidationError,
    ExecutionNotCancellableError,
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
from exceptions.mcp import (
    MCPConnectionError,
    MCPServerAlreadyExistsError,
    MCPServerNotFoundError,
)
from exceptions.network import BlockedURLError
from exceptions.node import (
    HTTPRequestError,
    NodeDataValidationError,
    NodeNotFoundError,
    TableSourceError,
    WebSearchConnectionError,
)
from exceptions.postgres_connection import (
    PostgresConnectionAlreadyExistsError,
    PostgresConnectionNotFoundError,
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
    "AuthSessionNotFoundError",
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
    "ExecutionApprovalNotPendingError",
    "ExecutionGraphValidationError",
    "ExecutionInputValidationError",
    "ExecutionNotCancellableError",
    "ExecutionNotFoundError",
    "HTTPRequestError",
    "LLMProviderAlreadyExistsError",
    "LLMProviderConfigError",
    "LLMProviderConnectionError",
    "LLMProviderNotFoundError",
    "MCPConnectionError",
    "MCPServerAlreadyExistsError",
    "MCPServerNotFoundError",
    "NodeDataValidationError",
    "NodeExecutionTimeoutError",
    "NodeNotFoundError",
    "PostgresConnectionAlreadyExistsError",
    "PostgresConnectionNotFoundError",
    "QuotaExceededError",
    "RateLimitExceededError",
    "TableSourceError",
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
