"""Workflow template API tests."""

from http import HTTPStatus

import pytest

from enums import InputNodeFormat, NodeType, OutputNodeFormat
from templates import (
    TEMPLATE_DEFINITIONS,
    TemplateDefinition,
    get_template_definition,
)
from tests.test_api.base import BaseTestCase


class TestWorkflowTemplateList(BaseTestCase):
    """Tests for GET /workflow-templates."""

    url = "/workflow-templates"

    @pytest.mark.asyncio
    async def test_lists_all_registered_templates(self) -> None:
        """Every registered template exposes complete picker metadata."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.get(url=self.url, headers=headers)

        data = await self.assert_response_list(response=response)
        if len(data) != len(TEMPLATE_DEFINITIONS):
            pytest.fail(
                f"Expected {len(TEMPLATE_DEFINITIONS)} templates, got {len(data)}"
            )

        keys = {item["key"] for item in data}
        expected_keys = {definition.key for definition in TEMPLATE_DEFINITIONS}
        if keys != expected_keys:
            pytest.fail(f"Template keys mismatch: {keys} != {expected_keys}")

        for item in data:
            self.assert_has_keys(
                item,
                {
                    "key",
                    "name",
                    "description",
                    "category",
                    "setup_steps",
                    "node_count",
                },
            )
            definition = get_template_definition(item["key"])
            if item["category"] != definition.category:
                pytest.fail("Template category did not match its definition")
            if item["setup_steps"] != list(definition.setup_steps):
                pytest.fail("Template setup steps did not match its definition")
            if item["node_count"] != len(definition.graph.nodes):
                pytest.fail("Template node count did not match its graph")


def test_email_auto_responder_template_uses_email_channel() -> None:
    """The email demo listens to and replies through unbound email accounts."""
    definition = get_template_definition("email-auto-responder")
    input_node, llm_node, output_node = definition.graph.nodes

    if input_node.type is not NodeType.INPUT:
        pytest.fail("Email template should start with an Input node")
    if input_node.data.get("format") != InputNodeFormat.EMAIL.value:
        pytest.fail("Email template Input should use the email format")
    if input_node.data.get("email_account_id") is not None:
        pytest.fail("Template Input should not reference a private email account")

    if llm_node.type is not NodeType.LLM:
        pytest.fail("Email template should draft its reply with an LLM node")

    if output_node.type is not NodeType.OUTPUT:
        pytest.fail("Email template should end with an Output node")
    if output_node.data.get("format") != OutputNodeFormat.EMAIL.value:
        pytest.fail("Email template Output should use the email format")
    if output_node.data.get("email_account_id") is not None:
        pytest.fail("Template Output should not reference a private email account")
    if output_node.data.get("email_to") or output_node.data.get("email_subject"):
        pytest.fail("Email template should reply to the triggering sender and subject")


def test_embeddable_web_chat_template_uses_public_chat_channel() -> None:
    """The web-chat starter exposes matching public Input and Output formats."""
    definition = get_template_definition("embeddable-web-chat")
    input_node, llm_node, output_node = definition.graph.nodes
    if input_node.data.get("format") != InputNodeFormat.WEB_CHAT.value:
        pytest.fail("Web-chat template Input should use the web_chat format")
    if llm_node.type is not NodeType.LLM:
        pytest.fail("Web-chat template should contain an LLM node")
    if output_node.data.get("format") != OutputNodeFormat.WEB_CHAT.value:
        pytest.fail("Web-chat template Output should use the web_chat format")


class TestWorkflowTemplateInstantiate(BaseTestCase):
    """Tests for POST /workflow-templates/{template_key}/instantiate."""

    url = "/workflow-templates"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("definition", TEMPLATE_DEFINITIONS, ids=lambda d: d.key)
    async def test_instantiate_builds_a_working_graph(
        self, definition: TemplateDefinition
    ) -> None:
        """Each template instantiates into a graph with matching node/edge counts."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.post(
            url=f"{self.url}/{definition.key}/instantiate",
            json={},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["name"] != definition.name:
            pytest.fail("Instantiated workflow should default to the template's name")

        nodes_response = await self.client.get(
            url=f"/nodes?workflow_id={data['id']}", headers=headers
        )
        nodes_data = await self.assert_response_list(response=nodes_response)
        if len(nodes_data) != len(definition.graph.nodes):
            message = (
                f"Expected {len(definition.graph.nodes)} nodes, got {len(nodes_data)}"
            )
            pytest.fail(message)

        edges_response = await self.client.get(
            url=f"/edges?workflow_id={data['id']}", headers=headers
        )
        edges_data = await self.assert_response_list(response=edges_response)
        if len(edges_data) != len(definition.graph.edges):
            message = (
                f"Expected {len(definition.graph.edges)} edges, got {len(edges_data)}"
            )
            pytest.fail(message)

    @pytest.mark.asyncio
    async def test_instantiate_with_custom_name(self) -> None:
        """A custom name overrides the template's default name."""
        _, headers = await self.create_user_and_get_token()
        key = TEMPLATE_DEFINITIONS[0].key

        response = await self.client.post(
            url=f"{self.url}/{key}/instantiate",
            json={"name": "my custom bot"},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["name"] != "my custom bot":
            pytest.fail("Custom name did not override the template's default name")

    @pytest.mark.asyncio
    async def test_unknown_template_key_rejected(self) -> None:
        """An unregistered template key returns 404."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.post(
            url=f"{self.url}/not-a-real-template/instantiate",
            json={},
            headers=headers,
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail(f"Expected {HTTPStatus.NOT_FOUND}, got {response.status_code}")
