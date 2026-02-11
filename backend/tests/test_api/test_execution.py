"""Execution API tests."""

from http import HTTPStatus

import pytest

from enums import ExecutionStatus, NodeType
from exceptions import ExecutionDispatchError
from integrations import PrefectExecutionRunner
from tests.factories import EdgeFactory, ExecutionFactory, NodeFactory, WorkflowFactory
from tests.test_api.base import BaseTestCase


class TestExecutionCreate(BaseTestCase):
    """Tests for POST /executions."""

    url = "/executions"

    @pytest.mark.asyncio
    async def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Successful run creation returns running execution."""

        async def fake_dispatch(_self: object, execution_id: int) -> str:
            """Return fake Prefect flow run ID."""
            return f"flow-run-{execution_id}"

        monkeypatch.setattr(
            PrefectExecutionRunner,
            "dispatch_execution",
            fake_dispatch,
        )

        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=output_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(
            data,
            {"id", "workflow_id", "status", "started_at", "prefect_flow_run_id"},
        )
        if data["workflow_id"] != workflow.id:
            pytest.fail("Execution workflow_id did not match request")
        if data["status"] != ExecutionStatus.RUNNING:
            pytest.fail("Execution status did not match running state")
        if data["prefect_flow_run_id"] != f"flow-run-{data['id']}":
            pytest.fail("Execution prefect_flow_run_id was not persisted")

    @pytest.mark.asyncio
    async def test_input_node_count_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Request fails if workflow has more than one input node."""

        async def fake_dispatch(_self: object, execution_id: int) -> str:
            """Return fake Prefect flow run ID."""
            return f"flow-run-{execution_id}"

        monkeypatch.setattr(
            PrefectExecutionRunner,
            "dispatch_execution",
            fake_dispatch,
        )

        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        first_input = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input 1", "format": "txt"},
        )
        second_input = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input 2", "format": "txt"},
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=first_input.id,
            target_node_id=output_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=second_input.id,
            target_node_id=output_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("Expected BAD_REQUEST for invalid input node count")

    @pytest.mark.asyncio
    async def test_output_node_count_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Request fails if workflow has more than one output node."""

        async def fake_dispatch(_self: object, execution_id: int) -> str:
            """Return fake Prefect flow run ID."""
            return f"flow-run-{execution_id}"

        monkeypatch.setattr(
            PrefectExecutionRunner,
            "dispatch_execution",
            fake_dispatch,
        )

        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        first_output = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output 1", "format": "txt"},
        )
        second_output = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output 2", "format": "txt"},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=first_output.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=second_output.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("Expected BAD_REQUEST for invalid output node count")

    @pytest.mark.asyncio
    async def test_cycle_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Request fails if workflow graph has a cycle."""

        async def fake_dispatch(_self: object, execution_id: int) -> str:
            """Return fake Prefect flow run ID."""
            return f"flow-run-{execution_id}"

        monkeypatch.setattr(
            PrefectExecutionRunner,
            "dispatch_execution",
            fake_dispatch,
        )

        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        llm_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.LLM,
            data={
                "label": "LLM",
                "llm_provider_id": 1,
                "model": "test-model",
                "system_prompt": "",
            },
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=llm_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=llm_node.id,
            target_node_id=output_node.id,
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=output_node.id,
            target_node_id=llm_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        if response.status_code != HTTPStatus.BAD_REQUEST:
            pytest.fail("Expected BAD_REQUEST for cyclic workflow graph")

    @pytest.mark.asyncio
    async def test_invalid_input_payload(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Request fails if input payload does not match txt contract."""

        async def fake_dispatch(_self: object, execution_id: int) -> str:
            """Return fake Prefect flow run ID."""
            return f"flow-run-{execution_id}"

        monkeypatch.setattr(
            PrefectExecutionRunner,
            "dispatch_execution",
            fake_dispatch,
        )

        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=output_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": 1}},
            headers=headers,
        )

        if response.status_code != HTTPStatus.UNPROCESSABLE_ENTITY:
            pytest.fail("Expected UNPROCESSABLE_ENTITY for invalid input payload")

    @pytest.mark.asyncio
    async def test_dispatch_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Request fails if execution dispatch to Prefect fails."""

        async def fake_dispatch(_self: object, execution_id: int) -> str:
            """Raise dispatch error for testing."""
            del execution_id
            raise ExecutionDispatchError(message="Prefect unavailable")

        monkeypatch.setattr(
            PrefectExecutionRunner,
            "dispatch_execution",
            fake_dispatch,
        )

        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )
        input_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.INPUT,
            data={"label": "Input", "format": "txt"},
        )
        output_node = await NodeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            type=NodeType.OUTPUT,
            data={"label": "Output", "format": "txt"},
        )
        await EdgeFactory.create_async(
            session=self.session,
            workflow_id=workflow.id,
            source_node_id=input_node.id,
            target_node_id=output_node.id,
        )

        response = await self.client.post(
            url=self.url,
            json={"workflow_id": workflow.id, "input_data": {"value": "hello"}},
            headers=headers,
        )

        if response.status_code != HTTPStatus.SERVICE_UNAVAILABLE:
            pytest.fail("Expected SERVICE_UNAVAILABLE for dispatch error")


class TestExecutionList(BaseTestCase):
    """Tests for GET /executions."""

    url = "/executions"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """List returns executions for the workflow."""
        user, headers = await self.create_user_and_get_token()
        workflow = await WorkflowFactory.create_async(
            session=self.session, owner_id=user["id"]
        )

        first = await ExecutionFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )
        second = await ExecutionFactory.create_async(
            session=self.session, workflow_id=workflow.id
        )

        response = await self.client.get(
            url=self.url,
            params={"workflow_id": workflow.id},
            headers=headers,
        )

        data = await self.assert_response_list(response=response)
        ids = {item.get("id") for item in data}
        if first.id not in ids or second.id not in ids:
            pytest.fail("Expected executions to appear in list")
