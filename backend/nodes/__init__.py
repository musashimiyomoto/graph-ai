"""Execution node handlers package."""

from nodes.approval import ApprovalNodeHandler
from nodes.base import NodeExecutionContext, NodeExecutionResult, NodeHandler, OnToken
from nodes.call_workflow import CallWorkflowNodeHandler
from nodes.code_transform import CodeTransformNodeHandler
from nodes.condition import ConditionNodeHandler, evaluate_condition
from nodes.definition import NodeDefinition, NodeHandlerDeps, ports_compatible
from nodes.http_request import HTTPRequestNodeHandler
from nodes.input import InputNodeHandler
from nodes.llm import LLMNodeHandler
from nodes.loop import LoopNodeHandler
from nodes.loop_input import LoopInputNodeHandler
from nodes.loop_output import LoopOutputNodeHandler
from nodes.mcp_tool import MCPToolNodeHandler
from nodes.output import OutputNodeHandler
from nodes.registry import (
    NODE_DEFINITIONS,
    NodeHandlerRegistry,
    build_node_catalog,
    check_edge_ports,
    check_source_handle,
    get_node_definition,
    get_node_output_handles,
)
from nodes.switch import (
    SwitchBranch,
    SwitchConfigurationError,
    SwitchNodeHandler,
    parse_switch_branches,
    select_switch_handle,
    switch_output_handles,
)
from nodes.table import TableNodeHandler
from nodes.template import TemplateNodeHandler
from nodes.vector_ingest import VectorIngestNodeHandler
from nodes.vector_search import VectorSearchNodeHandler
from nodes.web_search import WebSearchNodeHandler

__all__ = [
    "NODE_DEFINITIONS",
    "ApprovalNodeHandler",
    "CallWorkflowNodeHandler",
    "CodeTransformNodeHandler",
    "ConditionNodeHandler",
    "HTTPRequestNodeHandler",
    "InputNodeHandler",
    "LLMNodeHandler",
    "LoopInputNodeHandler",
    "LoopNodeHandler",
    "LoopOutputNodeHandler",
    "MCPToolNodeHandler",
    "NodeDefinition",
    "NodeExecutionContext",
    "NodeExecutionResult",
    "NodeHandler",
    "NodeHandlerDeps",
    "NodeHandlerRegistry",
    "OnToken",
    "OutputNodeHandler",
    "SwitchBranch",
    "SwitchConfigurationError",
    "SwitchNodeHandler",
    "TableNodeHandler",
    "TemplateNodeHandler",
    "VectorIngestNodeHandler",
    "VectorSearchNodeHandler",
    "WebSearchNodeHandler",
    "build_node_catalog",
    "check_edge_ports",
    "check_source_handle",
    "evaluate_condition",
    "get_node_definition",
    "get_node_output_handles",
    "parse_switch_branches",
    "ports_compatible",
    "select_switch_handle",
    "switch_output_handles",
]
