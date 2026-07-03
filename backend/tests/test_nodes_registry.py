"""Plugin node registry and typed-port compatibility tests."""

import pytest

from enums import NodeType, PortType
from nodes import (
    NODE_DEFINITIONS,
    build_node_catalog,
    check_edge_ports,
    get_node_definition,
    ports_compatible,
)


class TestRegistryCompleteness:
    """Tests that every node type is registered exactly once."""

    def test_every_type_has_one_definition(self) -> None:
        """Each NodeType maps to exactly one definition."""
        types = [definition.type for definition in NODE_DEFINITIONS]
        if sorted(types) != sorted(NodeType):
            pytest.fail("NODE_DEFINITIONS does not cover every NodeType exactly once")

    def test_catalog_covers_all_types(self) -> None:
        """The derived catalog contains an entry per node type."""
        catalog = build_node_catalog()
        if set(catalog) != set(NodeType):
            pytest.fail("Catalog does not cover every node type")

    def test_get_definition_returns_requested_type(self) -> None:
        """Lookup returns the definition for the requested type."""
        if get_node_definition(NodeType.LLM).type is not NodeType.LLM:
            pytest.fail("Lookup returned the wrong definition")


class TestCatalogPorts:
    """Tests that catalog entries expose port metadata."""

    def test_input_node_ports(self) -> None:
        """Input node has a text output and no input port."""
        graph = build_node_catalog()[NodeType.INPUT].graph
        if graph.input_port is not None or graph.output_port is not PortType.TEXT:
            pytest.fail("Input node ports are wrong")

    def test_output_node_ports(self) -> None:
        """Output node has a text input and no output port."""
        graph = build_node_catalog()[NodeType.OUTPUT].graph
        if graph.output_port is not None or graph.input_port is not PortType.TEXT:
            pytest.fail("Output node ports are wrong")


class TestPortCompatibility:
    """Tests for port compatibility checks."""

    def test_same_type_is_compatible(self) -> None:
        """Identical port types are compatible."""
        if not ports_compatible(PortType.TEXT, PortType.TEXT):
            pytest.fail("Matching ports should be compatible")

    def test_different_type_is_incompatible(self) -> None:
        """Different port types are not compatible."""
        if ports_compatible(PortType.TEXT, PortType.JSON):
            pytest.fail("Mismatched ports must be incompatible")

    def test_text_to_text_edge_ok(self) -> None:
        """A text output feeding a text input is valid."""
        if check_edge_ports(NodeType.INPUT, NodeType.OUTPUT) is not None:
            pytest.fail("input -> output should be a valid connection")

    def test_source_without_output_port_rejected(self) -> None:
        """A node without an output port cannot be a source."""
        if check_edge_ports(NodeType.OUTPUT, NodeType.INPUT) is None:
            pytest.fail("Output node has no output port and cannot be a source")

    def test_target_without_input_port_rejected(self) -> None:
        """A node without an input port cannot be a target."""
        if check_edge_ports(NodeType.INPUT, NodeType.INPUT) is None:
            pytest.fail("Input node has no input port and cannot be a target")
