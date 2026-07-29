"""Workflow-template enums."""

from enum import StrEnum, auto


class TemplateSettingsSection(StrEnum):
    """Settings destinations that a workflow template can require."""

    CONNECTIONS = auto()
    PROVIDERS = auto()
    TELEGRAM = auto()
    EMAIL = auto()
    POSTGRES = auto()
    MCP = auto()
    VECTORS = auto()
