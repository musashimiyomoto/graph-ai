"""Workflow template API tests."""

from http import HTTPStatus

import pytest

from templates import TEMPLATE_DEFINITIONS, TemplateDefinition
from tests.test_api.base import BaseTestCase


class TestWorkflowTemplateList(BaseTestCase):
    """Tests for GET /workflow-templates."""

    url = "/workflow-templates"

    @pytest.mark.asyncio
    async def test_lists_all_registered_templates(self) -> None:
        """Every registered template shows up with its key/name/description."""
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
            self.assert_has_keys(item, {"key", "name", "description"})


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
