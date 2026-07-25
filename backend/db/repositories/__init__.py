"""Repository interfaces for database access."""

from db.repositories.artifact import ArtifactRepository
from db.repositories.audit_log import AuditLogRepository
from db.repositories.auth_action_token import AuthActionTokenRepository
from db.repositories.auth_session import AuthSessionRepository
from db.repositories.connection import (
    ConnectionOAuthStateRepository,
    ConnectionRepository,
)
from db.repositories.conversation import ConversationRepository
from db.repositories.edge import EdgeRepository
from db.repositories.email_account import EmailAccountRepository
from db.repositories.execution import ExecutionRepository
from db.repositories.knowledge_collection import KnowledgeCollectionRepository
from db.repositories.knowledge_source import KnowledgeSourceRepository
from db.repositories.llm_provider import LLMProviderRepository
from db.repositories.mcp_server import MCPServerRepository
from db.repositories.node import NodeRepository
from db.repositories.node_execution import NodeExecutionRepository
from db.repositories.node_schedule import NodeScheduleRepository
from db.repositories.postgres_connection import PostgresConnectionRepository
from db.repositories.state_entry import (
    StateEntryHistoryRepository,
    StateEntryRepository,
)
from db.repositories.telegram_bot import TelegramBotRepository
from db.repositories.usage_record import UsageRecordRepository
from db.repositories.user import UserRepository
from db.repositories.workflow import WorkflowRepository
from db.repositories.workflow_version import WorkflowVersionRepository

__all__ = [
    "ArtifactRepository",
    "AuditLogRepository",
    "AuthActionTokenRepository",
    "AuthSessionRepository",
    "ConnectionOAuthStateRepository",
    "ConnectionRepository",
    "ConversationRepository",
    "EdgeRepository",
    "EmailAccountRepository",
    "ExecutionRepository",
    "KnowledgeCollectionRepository",
    "KnowledgeSourceRepository",
    "LLMProviderRepository",
    "MCPServerRepository",
    "NodeExecutionRepository",
    "NodeRepository",
    "NodeScheduleRepository",
    "PostgresConnectionRepository",
    "StateEntryHistoryRepository",
    "StateEntryRepository",
    "TelegramBotRepository",
    "UsageRecordRepository",
    "UserRepository",
    "WorkflowRepository",
    "WorkflowVersionRepository",
]
