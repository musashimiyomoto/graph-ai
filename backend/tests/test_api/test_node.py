"""Node API tests."""

import uuid
from http import HTTPStatus

import pytest
from httpx import AsyncClient, Response

from db.models import NodeSchedule
from db.repositories import NodeScheduleRepository
from enums import NodeType
from enums.node import InputNodeFormat, OutputNodeFormat
from tests.factories import LLMProviderFactory, NodeFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase


def _extra_fields_by_type(node_type: NodeType, *, llm_provider_id: int | None) -> dict:
    """Return the type-specific fields for a node data payload."""
    by_type: dict[NodeType, dict] = {
        NodeType.INPUT: {"format": InputNodeFormat.TXT},
        NodeType.LLM: {
            "llm_provider_id": llm_provider_id,
            "model": "gpt-4",
            "system_prompt": "You are a helpful assistant.",
        },
        NodeType.WEB_SEARCH: {"max_results": 5},
        NodeType.TEMPLATE: {"template": "Summary: {{input}}"},
        NodeType.HTTP_REQUEST: {
            "url": "https://api.example.com/endpoint",
            "method": "get",
        },
        NodeType.CONDITION: {
            "condition_type": "contains",
            "value": "hello",
            "case_sensitive": "false",
        },
        NodeType.CODE_TRANSFORM: {"code": "output = input"},
        NodeType.VECTOR_INGEST: {"collection": "docs"},
        NodeType.VECTOR_SEARCH: {"collection": "docs", "top_k": 4},
        NodeType.LOOP: {"mode": "list"},
        NodeType.LOOP_INPUT: {},
        NodeType.LOOP_OUTPUT: {},
        NodeType.OUTPUT: {"format": OutputNodeFormat.TXT},
    }
    return by_type[node_type]


def build_node_data(node_type: NodeType, *, llm_provider_id: int | None = None) -> dict:
    """Build node data payloads for tests."""
    return {
        "label": f"node-{uuid.uuid4().hex[:8]}",
        **_extra_fields_by_type(node_type, llm_provider_id=llm_provider_id),
    }


EXPECTED_FIELDS_BY_TYPE: dict[NodeType, set[str]] = {
    NodeType.INPUT: {"label", "format"},
    NodeType.LLM: {"label", "llm_provider_id", "model", "system_prompt"},
    NodeType.WEB_SEARCH: {"label", "max_results"},
    NodeType.TEMPLATE: {"label", "template"},
    NodeType.HTTP_REQUEST: {"label", "url", "method"},
    NodeType.CONDITION: {"label", "condition_type", "value", "case_sensitive"},
    NodeType.CODE_TRANSFORM: {"label", "code"},
    NodeType.VECTOR_INGEST: {"label", "collection"},
    NodeType.VECTOR_SEARCH: {"label", "collection", "top_k"},
    NodeType.LOOP: {"label", "mode"},
    NodeType.LOOP_INPUT: {"label"},
    NodeType.LOOP_OUTPUT: {"label"},
    NodeType.OUTPUT: {"label", "format", "webhook_url"},
}

# Node types whose top-level "exactly one input/output" semantics are
# scope-specific — they need a real Loop node as parent_node_id to be
# creatable at all (LOOP_INPUT/LOOP_OUTPUT), or must never receive one
# (everything else). Centralizes the create-payload scope logic the
# parametrized CRUD tests below all need.
_LOOP_BODY_ONLY_TYPES = {NodeType.LOOP_INPUT, NodeType.LOOP_OUTPUT}


async def _create_node_with_scope(
    client: AsyncClient,
    headers: dict,
    workflow_id: int,
    node_type: NodeType,
    *,
    llm_provider_id: int | None = None,
) -> Response:
    """POST /nodes with parent_node_id resolved for scope-only node types.

    For `LOOP_INPUT`/`LOOP_OUTPUT`, first creates a real Loop node in the
    workflow and points `parent_node_id` at it, since those types are only
    creatable inside a Loop node's body.
    """
    parent_node_id = None
    if node_type in _LOOP_BODY_ONLY_TYPES:
        loop_response = await client.post(
            url="/nodes",
            json={
                "workflow_id": workflow_id,
                "type": NodeType.LOOP,
                "data": build_node_data(NodeType.LOOP),
            },
            headers=headers,
        )
        parent_node_id = loop_response.json()["id"]

    payload = {
        "workflow_id": workflow_id,
        "type": node_type,
        "data": build_node_data(node_type, llm_provider_id=llm_provider_id),
        "parent_node_id": parent_node_id,
    }
    return await client.post(url="/nodes", json=payload, headers=headers)


class TestNodeCreate(BaseTestCase):
    """Tests for POST /nodes."""

    url = "/nodes"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("node_type", list(NodeType))
    async def test_ok(self, node_type: NodeType) -> None:
        """Successful creation returns node data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session,
            owner_id=user["id"],
        )
        llm_provider_id = None
        if node_type is NodeType.LLM:
            provider = await LLMProviderFactory.create_async(
                session=self.session,
                user_id=user["id"],
            )
            llm_provider_id = provider.id

        response = await _create_node_with_scope(
            client=self.client,
            headers=headers,
            workflow_id=workflow.id,
            node_type=node_type,
            llm_provider_id=llm_provider_id,
        )

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(
            data,
            {"id", "workflow_id", "type", "data", "position_x", "position_y"},
        )
        if data["workflow_id"] != workflow.id:
            pytest.fail("Node workflow_id did not match request")
        if data["type"] != node_type:
            pytest.fail(f"Node type did not match: {data['type']} != {node_type}")

    @pytest.mark.asyncio
    async def test_llm_provider_not_found(self) -> None:
        """LLM nodes must reference existing providers."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session,
            owner_id=user["id"],
        )

        payload = {
            "workflow_id": workflow.id,
            "type": NodeType.LLM,
            "data": build_node_data(NodeType.LLM, llm_provider_id=9999),
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail(f"Expected {HTTPStatus.NOT_FOUND}, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_http_request_malformed_headers_rejected(self) -> None:
        """Malformed JSON in the headers field is rejected at save time."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        payload = {
            "workflow_id": workflow.id,
            "type": NodeType.HTTP_REQUEST,
            "data": {
                **build_node_data(NodeType.HTTP_REQUEST),
                "headers": "{not valid json",
            },
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        expected = HTTPStatus.UNPROCESSABLE_ENTITY
        if response.status_code != expected:
            pytest.fail(f"Expected {expected}, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_llm_non_string_system_prompt_rejected(self) -> None:
        """A non-string system_prompt is rejected at save time."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"]
        )

        payload = {
            "workflow_id": workflow.id,
            "type": NodeType.LLM,
            "data": {
                **build_node_data(NodeType.LLM, llm_provider_id=provider.id),
                "system_prompt": 123,
            },
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        expected = HTTPStatus.UNPROCESSABLE_ENTITY
        if response.status_code != expected:
            pytest.fail(f"Expected {expected}, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_invalid_cron_expression_rejected(self) -> None:
        """A malformed cron expression is rejected at save time."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        payload = {
            "workflow_id": workflow.id,
            "type": NodeType.INPUT,
            "data": {
                "label": "Scheduled input",
                "format": InputNodeFormat.SCHEDULE,
                "cron_expression": "not a cron",
            },
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        expected = HTTPStatus.UNPROCESSABLE_ENTITY
        if response.status_code != expected:
            pytest.fail(f"Expected {expected}, got {response.status_code}")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("webhook_url", [None, "/relative-callback"])
    async def test_webhook_output_requires_absolute_callback_url(
        self, webhook_url: str | None
    ) -> None:
        """Webhook Output requires a configured absolute HTTP(S) callback URL."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        data = {"label": "Webhook Output", "format": OutputNodeFormat.WEBHOOK}
        if webhook_url is not None:
            data["webhook_url"] = webhook_url

        response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "type": NodeType.OUTPUT,
                "data": data,
            },
            headers=headers,
        )

        expected = HTTPStatus.UNPROCESSABLE_ENTITY
        if response.status_code != expected:
            pytest.fail(f"Expected {expected}, got {response.status_code}")


class TestNodeLoopScoping(BaseTestCase):
    """Tests for the parent_node_id / Loop-body scope invariants."""

    url = "/nodes"

    async def _create_loop(self, headers: dict, workflow_id: int) -> int:
        """Create a top-level Loop node and return its id."""
        response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow_id,
                "type": NodeType.LOOP,
                "data": build_node_data(NodeType.LOOP),
            },
            headers=headers,
        )
        return (await self.assert_response_dict(response=response))["id"]

    @pytest.mark.asyncio
    async def test_loop_input_requires_a_parent(self) -> None:
        """LOOP_INPUT can't be created at the top level (parent_node_id=None)."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "type": NodeType.LOOP_INPUT,
                "data": build_node_data(NodeType.LOOP_INPUT),
            },
            headers=headers,
        )

        expected = HTTPStatus.UNPROCESSABLE_ENTITY
        if response.status_code != expected:
            pytest.fail(f"Expected {expected}, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_loop_output_requires_a_parent(self) -> None:
        """LOOP_OUTPUT can't be created at the top level (parent_node_id=None)."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "type": NodeType.LOOP_OUTPUT,
                "data": build_node_data(NodeType.LOOP_OUTPUT),
            },
            headers=headers,
        )

        expected = HTTPStatus.UNPROCESSABLE_ENTITY
        if response.status_code != expected:
            pytest.fail(f"Expected {expected}, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_input_rejected_inside_a_loop_body(self) -> None:
        """A top-level INPUT node can't be created inside a Loop node's body."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        loop_id = await self._create_loop(headers=headers, workflow_id=workflow.id)

        response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "type": NodeType.INPUT,
                "data": build_node_data(NodeType.INPUT),
                "parent_node_id": loop_id,
            },
            headers=headers,
        )

        expected = HTTPStatus.UNPROCESSABLE_ENTITY
        if response.status_code != expected:
            pytest.fail(f"Expected {expected}, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_output_rejected_inside_a_loop_body(self) -> None:
        """A top-level OUTPUT node can't be created inside a Loop node's body."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        loop_id = await self._create_loop(headers=headers, workflow_id=workflow.id)

        response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "type": NodeType.OUTPUT,
                "data": build_node_data(NodeType.OUTPUT),
                "parent_node_id": loop_id,
            },
            headers=headers,
        )

        expected = HTTPStatus.UNPROCESSABLE_ENTITY
        if response.status_code != expected:
            pytest.fail(f"Expected {expected}, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_nested_loop_rejected(self) -> None:
        """A Loop node cannot be created inside another Loop node's body."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        outer_loop_id = await self._create_loop(
            headers=headers, workflow_id=workflow.id
        )

        response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "type": NodeType.LOOP,
                "data": build_node_data(NodeType.LOOP),
                "parent_node_id": outer_loop_id,
            },
            headers=headers,
        )

        expected = HTTPStatus.UNPROCESSABLE_ENTITY
        if response.status_code != expected:
            pytest.fail(f"Expected {expected}, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_parent_node_id_must_reference_a_loop_node(self) -> None:
        """A non-Loop node can't be used as a parent scope."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        not_a_loop = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.TEMPLATE,
            data=build_node_data(NodeType.TEMPLATE),
        )

        response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "type": NodeType.LOOP_INPUT,
                "data": build_node_data(NodeType.LOOP_INPUT),
                "parent_node_id": not_a_loop.id,
            },
            headers=headers,
        )

        expected = HTTPStatus.UNPROCESSABLE_ENTITY
        if response.status_code != expected:
            pytest.fail(f"Expected {expected}, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_deleting_loop_cascades_to_body_nodes(self) -> None:
        """Deleting a Loop node deletes its body nodes via ON DELETE CASCADE."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        loop_id = await self._create_loop(headers=headers, workflow_id=workflow.id)
        body_response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "type": NodeType.LOOP_INPUT,
                "data": build_node_data(NodeType.LOOP_INPUT),
                "parent_node_id": loop_id,
            },
            headers=headers,
        )
        body_node_id = (await self.assert_response_dict(response=body_response))["id"]

        response = await self.client.delete(
            url=f"{self.url}/{loop_id}", headers=headers
        )
        await self.assert_response_ok(response=response)

        fetch = await self.client.get(
            url=self.url, params={"workflow_id": workflow.id}, headers=headers
        )
        data = await self.assert_response_list(response=fetch)
        ids = {item.get("id") for item in data}
        if body_node_id in ids:
            pytest.fail("Loop body node should have been cascade-deleted")


class TestNodeSchedule(BaseTestCase):
    """Tests for the NodeSchedule row kept in sync with a scheduled Input node."""

    url = "/nodes"

    async def _get_schedule(self, node_id: int) -> NodeSchedule | None:
        """Fetch the NodeSchedule row for a node, if any."""
        self.session.expire_all()
        return await NodeScheduleRepository().get_by(
            session=self.session, node_id=node_id
        )

    @pytest.mark.asyncio
    async def test_creating_a_scheduled_input_creates_a_schedule_row(self) -> None:
        """Saving format=schedule with a cron expression creates a schedule row."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        payload = {
            "workflow_id": workflow.id,
            "type": NodeType.INPUT,
            "data": {
                "label": "Scheduled input",
                "format": InputNodeFormat.SCHEDULE,
                "cron_expression": "0 9 * * *",
            },
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)
        data = await self.assert_response_dict(response=response)

        schedule = await self._get_schedule(node_id=data["id"])
        if schedule is None or schedule.cron_expression != "0 9 * * *":
            pytest.fail("Expected a schedule row matching the node's cron expression")

    @pytest.mark.asyncio
    async def test_updating_cron_expression_updates_the_schedule_row(self) -> None:
        """Editing the cron expression updates the existing schedule row in place."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={
                "label": "Scheduled input",
                "format": InputNodeFormat.SCHEDULE,
                "cron_expression": "0 9 * * *",
            },
        )

        response = await self.client.patch(
            url=f"{self.url}/{node.id}",
            json={
                "data": {
                    "label": "Scheduled input",
                    "format": InputNodeFormat.SCHEDULE,
                    "cron_expression": "*/15 * * * *",
                }
            },
            headers=headers,
        )
        await self.assert_response_dict(response=response)

        schedule = await self._get_schedule(node_id=node.id)
        if schedule is None or schedule.cron_expression != "*/15 * * * *":
            pytest.fail("Expected the schedule row's cron expression to be updated")

    @pytest.mark.asyncio
    async def test_switching_away_from_schedule_removes_the_schedule_row(self) -> None:
        """Changing format away from schedule removes the now-irrelevant row."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        create_response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "type": NodeType.INPUT,
                "data": {
                    "label": "Scheduled input",
                    "format": InputNodeFormat.SCHEDULE,
                    "cron_expression": "0 9 * * *",
                },
            },
            headers=headers,
        )
        node_data = await self.assert_response_dict(response=create_response)
        if await self._get_schedule(node_id=node_data["id"]) is None:
            pytest.fail("Expected a schedule row to exist before the switch")

        response = await self.client.patch(
            url=f"{self.url}/{node_data['id']}",
            json={"data": {"label": "Plain input", "format": InputNodeFormat.TXT}},
            headers=headers,
        )
        await self.assert_response_dict(response=response)

        if await self._get_schedule(node_id=node_data["id"]) is not None:
            pytest.fail("Expected the schedule row to be removed after format switch")

    @pytest.mark.asyncio
    async def test_deleting_the_node_removes_the_schedule_row(self) -> None:
        """Deleting a scheduled Input node cascades to its schedule row."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        create_response = await self.client.post(
            url=self.url,
            json={
                "workflow_id": workflow.id,
                "type": NodeType.INPUT,
                "data": {
                    "label": "Scheduled input",
                    "format": InputNodeFormat.SCHEDULE,
                    "cron_expression": "0 9 * * *",
                },
            },
            headers=headers,
        )
        node_data = await self.assert_response_dict(response=create_response)
        if await self._get_schedule(node_id=node_data["id"]) is None:
            pytest.fail("Expected a schedule row to exist before deletion")

        response = await self.client.delete(
            url=f"{self.url}/{node_data['id']}", headers=headers
        )
        await self.assert_response_ok(response=response)

        if await self._get_schedule(node_id=node_data["id"]) is not None:
            pytest.fail("Expected the schedule row to be gone after node deletion")


class TestNodeList(BaseTestCase):
    """Tests for GET /nodes."""

    url = "/nodes"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """List returns nodes for the workflow."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session,
            owner_id=user["id"],
        )

        first = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
        )
        second = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data=build_node_data(NodeType.OUTPUT),
        )

        response = await self.client.get(
            url=self.url,
            params={"workflow_id": workflow.id},
            headers=headers,
        )

        data = await self.assert_response_list(response=response)
        ids = {item.get("id") for item in data}
        if first.id not in ids or second.id not in ids:
            pytest.fail("Expected nodes to appear in list")


class TestNodeCatalog(BaseTestCase):
    """Tests for GET /nodes/catalog."""

    url = "/nodes/catalog"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Catalog contains all node types and field schemas."""
        response = await self.client.get(url=self.url)

        data = await self.assert_response_list(response=response)
        types = {item["type"] for item in data}
        if types != set(NodeType):
            pytest.fail(f"Unexpected node types in catalog: {types}")

        for item in data:
            self.assert_has_keys(
                item,
                {"type", "label", "icon_key", "graph", "fields"},
            )
            field_names = {
                field["name"]
                for field in item["fields"]
                if isinstance(field, dict) and "name" in field
            }
            expected = EXPECTED_FIELDS_BY_TYPE[NodeType(item["type"])]
            if not expected.issubset(field_names):
                missing = expected - field_names
                pytest.fail(f"Missing expected fields for {item['type']}: {missing}")


class TestNodeUpdate(BaseTestCase):
    """Tests for PATCH /nodes/{node_id}."""

    url = "/nodes"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("node_type", list(NodeType))
    async def test_ok(self, node_type: NodeType) -> None:
        """Successful update returns updated node data."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session,
            owner_id=user["id"],
        )
        llm_provider_id = None
        if node_type is NodeType.LLM:
            provider = await LLMProviderFactory.create_async(
                session=self.session,
                user_id=user["id"],
            )
            llm_provider_id = provider.id
        parent_node_id = None
        if node_type in _LOOP_BODY_ONLY_TYPES:
            loop_node = await NodeFactory.create_async(
                session=self.session,
                workflow_id=workflow.id,
                type=NodeType.LOOP,
                data=build_node_data(NodeType.LOOP),
            )
            parent_node_id = loop_node.id
        node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=node_type,
            data=build_node_data(node_type, llm_provider_id=llm_provider_id),
            parent_node_id=parent_node_id,
        )
        new_x = 42.0
        new_y = 24.0

        response = await self.client.patch(
            url=f"{self.url}/{node.id}",
            json={
                "data": build_node_data(node_type, llm_provider_id=llm_provider_id),
                "position_x": new_x,
                "position_y": new_y,
            },
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["position_x"] != new_x or data["position_y"] != new_y:
            pytest.fail("Node positions were not updated")


class TestNodeDelete(BaseTestCase):
    """Tests for DELETE /nodes/{node_id}."""

    url = "/nodes"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("node_type", list(NodeType))
    async def test_ok(self, node_type: NodeType) -> None:
        """Successful delete removes the node."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session,
            owner_id=user["id"],
        )
        parent_node_id = None
        if node_type in _LOOP_BODY_ONLY_TYPES:
            loop_node = await NodeFactory.create_async(
                session=self.session,
                workflow_id=workflow.id,
                type=NodeType.LOOP,
                data=build_node_data(NodeType.LOOP),
            )
            parent_node_id = loop_node.id
        node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=node_type,
            data=build_node_data(
                node_type,
                llm_provider_id=(
                    (
                        await LLMProviderFactory.create_async(
                            session=self.session,
                            user_id=user["id"],
                        )
                    ).id
                    if node_type is NodeType.LLM
                    else None
                ),
            ),
            parent_node_id=parent_node_id,
        )

        response = await self.client.delete(
            url=f"{self.url}/{node.id}",
            headers=headers,
        )

        await self.assert_response_ok(response=response)

        fetch = await self.client.get(
            url=self.url,
            params={"workflow_id": workflow.id},
            headers=headers,
        )
        data = await self.assert_response_list(response=fetch)
        ids = {item.get("id") for item in data}
        if node.id in ids:
            pytest.fail("Expected deleted node to not appear in list")
