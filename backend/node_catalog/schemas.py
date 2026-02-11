"""Schemas for node catalog definitions."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from enums import NodeType, ValidatorType


class NodeFieldWidget(StrEnum):
    """UI widgets supported by node field rendering."""

    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    SELECT = "select"
    PROVIDER = "provider"
    MODEL = "model"


class NodeFieldDataSourceKind(StrEnum):
    """Dynamic data source kinds for node fields."""

    LLM_PROVIDER = "llm_provider"
    LLM_MODEL = "llm_model"


@dataclass(frozen=True)
class NodeFieldUI:
    """UI metadata for a node field."""

    widget: NodeFieldWidget
    label: str
    placeholder: str | None = None
    help: str | None = None


@dataclass(frozen=True)
class NodeFieldDataSource:
    """Dynamic source definition for a node field."""

    kind: NodeFieldDataSourceKind
    depends_on: str | None = None


@dataclass(frozen=True)
class NodeFieldSpec:
    """Schema definition for a single node data field."""

    name: str
    required: bool
    validators: dict[ValidatorType, Any]
    ui: NodeFieldUI
    default: Any | None = None
    datasource: NodeFieldDataSource | None = None


@dataclass(frozen=True)
class NodeGraphSpec:
    """Graph-connection metadata for a node type."""

    has_input: bool
    has_output: bool


@dataclass(frozen=True)
class NodeCatalogItem:
    """Full metadata entry for a node type."""

    type: NodeType
    label: str
    icon_key: str
    graph: NodeGraphSpec
    defaults: dict[str, Any]
    fields: tuple[NodeFieldSpec, ...]
