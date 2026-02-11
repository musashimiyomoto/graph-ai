"""Execution use case implementation."""

from collections import deque
from datetime import UTC, datetime
from typing import cast

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from enums import ExecutionStatus, NodeType
from exceptions import (
    ExecutionDispatchError,
    ExecutionGraphValidationError,
    ExecutionInputValidationError,
    ExecutionNotFoundError,
    LLMProviderConnectionError,
    WorkflowNotFoundError,
)
from integrations import LLMClientFactory, PrefectExecutionRunner
from models import Edge, Execution, Node
from repositories import (
    EdgeRepository,
    ExecutionRepository,
    LLMProviderRepository,
    NodeRepository,
    WorkflowRepository,
)
from schemas import ChatMessage


class ExecutionUsecase:
    """Execution business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._execution_repository = ExecutionRepository()
        self._workflow_repository = WorkflowRepository()
        self._node_repository = NodeRepository()
        self._edge_repository = EdgeRepository()
        self._provider_repository = LLMProviderRepository()
        self._llm_client_factory = LLMClientFactory()
        self._prefect_runner = PrefectExecutionRunner()

    async def create_execution(
        self,
        session: AsyncSession,
        user_id: int,
        workflow_id: int,
        input_data: dict | None = None,
    ) -> Execution:
        """Create and dispatch execution for a workflow.

        Args:
            session: The session.
            user_id: The owner user ID.
            workflow_id: The workflow ID.
            input_data: The execution input data.

        Returns:
            The created execution.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.
            ExecutionGraphValidationError: If graph is invalid for execution.
            ExecutionInputValidationError: If input payload is invalid.
            ExecutionDispatchError: If execution dispatch fails.

        """
        workflow = await self._workflow_repository.get_by(
            session=session,
            id=workflow_id,
            owner_id=user_id,
        )
        if not workflow:
            raise WorkflowNotFoundError

        nodes = await self._node_repository.get_all(
            session=session,
            workflow_id=workflow_id,
        )
        edges = await self._edge_repository.get_all(
            session=session,
            workflow_id=workflow_id,
        )

        self._build_graph_context(nodes=nodes, edges=edges)
        self._validate_input_payload(input_data=input_data)

        execution = await self._execution_repository.create(
            session=session,
            data={
                "workflow_id": workflow_id,
                "input_data": input_data,
                "status": ExecutionStatus.RUNNING,
            },
        )

        try:
            prefect_flow_run_id = await self._prefect_runner.dispatch_execution(
                execution_id=execution.id
            )
        except ExecutionDispatchError as exc:
            await self._execution_repository.update_by(
                session=session,
                id=execution.id,
                data={
                    "status": ExecutionStatus.FAILED,
                    "error": str(exc.message),
                    "finished_at": datetime.now(tz=UTC).replace(tzinfo=None),
                },
            )
            raise

        updated_execution = await self._execution_repository.update_by(
            session=session,
            id=execution.id,
            data={"prefect_flow_run_id": prefect_flow_run_id},
        )
        if updated_execution is None:
            raise ExecutionDispatchError(message="Execution was not persisted")

        return updated_execution

    async def get_executions(
        self, session: AsyncSession, user_id: int, workflow_id: int
    ) -> list[Execution]:
        """List executions for a workflow.

        Args:
            session: The session.
            user_id: The owner user ID.
            workflow_id: The workflow ID.

        Returns:
            The list of executions.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        return await self._execution_repository.get_all(
            session=session, workflow_id=workflow_id
        )

    async def get_execution(
        self, session: AsyncSession, execution_id: int, user_id: int
    ) -> Execution:
        """Fetch an execution by ID.

        Args:
            session: The session.
            execution_id: The execution ID.
            user_id: The owner user ID.

        Returns:
            The execution.

        Raises:
            ExecutionNotFoundError: If the execution is not found.
            WorkflowNotFoundError: If the workflow is not found.

        """
        execution = await self._execution_repository.get_by(
            session=session, id=execution_id
        )
        if not execution:
            raise ExecutionNotFoundError

        workflow = await self._workflow_repository.get_by(
            session=session, id=execution.workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        return execution

    async def run_execution(
        self,
        session: AsyncSession,
        execution_id: int,
    ) -> dict[str, str]:
        """Execute workflow nodes for an execution and return output payload.

        Args:
            session: Database session.
            execution_id: Execution ID.

        Returns:
            Output payload.

        Raises:
            ExecutionNotFoundError: If execution is not found.
            WorkflowNotFoundError: If workflow is not found.
            ExecutionGraphValidationError: If graph is invalid.
            ExecutionInputValidationError: If input payload is invalid.

        """
        execution = await self._execution_repository.get_by(
            session=session,
            id=execution_id,
        )
        if execution is None:
            raise ExecutionNotFoundError

        workflow = await self._workflow_repository.get_by(
            session=session,
            id=execution.workflow_id,
        )
        if workflow is None:
            raise WorkflowNotFoundError

        nodes = await self._node_repository.get_all(
            session=session,
            workflow_id=execution.workflow_id,
        )
        edges = await self._edge_repository.get_all(
            session=session,
            workflow_id=execution.workflow_id,
        )

        graph = self._build_graph_context(nodes=nodes, edges=edges)
        nodes_by_id = cast("dict[int, Node]", graph["nodes_by_id"])
        inbound = cast("dict[int, list[int]]", graph["inbound"])
        topological_order = cast("list[int]", graph["topological_order"])
        output_node_id = cast("int", graph["output_node_id"])

        input_value = self._extract_input_value(input_data=execution.input_data)
        outputs_by_node: dict[int, str] = {}
        for node_id in topological_order:
            node = nodes_by_id[node_id]
            if node.type is NodeType.INPUT:
                outputs_by_node[node_id] = input_value
                continue

            parent_values = [
                outputs_by_node[parent_id] for parent_id in inbound[node_id]
            ]
            if not parent_values:
                message = f"Node {node.id} does not have input value"
                raise ExecutionGraphValidationError(message=message)

            if node.type is NodeType.LLM:
                outputs_by_node[node_id] = await self._execute_llm_node(
                    session=session,
                    workflow_owner_id=workflow.owner_id,
                    node_data=node.data,
                    parent_values=parent_values,
                )
                continue

            if node.type is NodeType.OUTPUT:
                outputs_by_node[node_id] = "\n".join(parent_values)
                continue

            message = f"Unsupported node type: {node.type}"
            raise ExecutionGraphValidationError(message=message)

        return {"value": outputs_by_node[output_node_id]}

    async def execute_and_finalize(
        self,
        session: AsyncSession,
        execution_id: int,
    ) -> None:
        """Run execution and persist terminal status.

        Args:
            session: Database session.
            execution_id: Execution ID.

        Raises:
            Exception: Re-raises execution errors after persisting failed status.

        """
        try:
            output_data = await self.run_execution(
                session=session,
                execution_id=execution_id,
            )
            await self.mark_execution_success(
                session=session,
                execution_id=execution_id,
                output_data=output_data,
            )
        except Exception as exc:
            await self.mark_execution_failed(
                session=session,
                execution_id=execution_id,
                error=str(exc),
            )
            raise

    async def mark_execution_success(
        self,
        session: AsyncSession,
        execution_id: int,
        output_data: dict[str, str],
    ) -> Execution:
        """Persist successful execution result.

        Args:
            session: Database session.
            execution_id: Execution ID.
            output_data: Final output payload.

        Returns:
            Updated execution.

        Raises:
            ExecutionNotFoundError: If execution record does not exist.

        """
        updated_execution = await self._execution_repository.update_by(
            session=session,
            id=execution_id,
            data={
                "status": ExecutionStatus.SUCCESS,
                "output_data": output_data,
                "error": None,
                "finished_at": datetime.now(tz=UTC).replace(tzinfo=None),
            },
        )
        if updated_execution is None:
            raise ExecutionNotFoundError

        return updated_execution

    async def mark_execution_failed(
        self,
        session: AsyncSession,
        execution_id: int,
        error: str,
    ) -> Execution:
        """Persist failed execution result.

        Args:
            session: Database session.
            execution_id: Execution ID.
            error: Failure reason.

        Returns:
            Updated execution.

        Raises:
            ExecutionNotFoundError: If execution record does not exist.

        """
        updated_execution = await self._execution_repository.update_by(
            session=session,
            id=execution_id,
            data={
                "status": ExecutionStatus.FAILED,
                "error": error,
                "finished_at": datetime.now(tz=UTC).replace(tzinfo=None),
            },
        )
        if updated_execution is None:
            raise ExecutionNotFoundError

        return updated_execution

    def _validate_input_payload(self, input_data: dict | None) -> None:
        """Validate execution input payload contract for API creation.

        Args:
            input_data: Input payload.

        Raises:
            ExecutionInputValidationError: If payload is invalid.

        """
        if input_data is None:
            raise ExecutionInputValidationError(
                message="Input payload is required for txt format"
            )

        if not isinstance(input_data, dict):
            raise ExecutionInputValidationError(
                message="Input payload must be an object"
            )

        if not isinstance(input_data.get("value"), str):
            raise ExecutionInputValidationError(
                message="Input payload field 'value' must be a string"
            )

    def _build_graph_context(
        self,
        nodes: list[Node],
        edges: list[Edge],
    ) -> dict[str, object]:
        """Build and validate graph context for execution.

        Args:
            nodes: Workflow nodes.
            edges: Workflow edges.

        Returns:
            Validated graph context.

        Raises:
            ExecutionGraphValidationError: If graph is invalid.

        """
        if not nodes:
            message = "Workflow must contain at least one node"
            raise ExecutionGraphValidationError(message=message)

        input_nodes = [node for node in nodes if node.type is NodeType.INPUT]
        if len(input_nodes) != 1:
            message = "Workflow must contain exactly one input node"
            raise ExecutionGraphValidationError(message=message)

        output_nodes = [node for node in nodes if node.type is NodeType.OUTPUT]
        if len(output_nodes) != 1:
            message = "Workflow must contain exactly one output node"
            raise ExecutionGraphValidationError(message=message)

        nodes_by_id = {node.id: node for node in nodes}
        outbound: dict[int, list[int]] = {node.id: [] for node in nodes}
        inbound: dict[int, list[int]] = {node.id: [] for node in nodes}
        indegree: dict[int, int] = {node.id: 0 for node in nodes}
        for edge in edges:
            source_id = edge.source_node_id
            target_id = edge.target_node_id
            if source_id not in nodes_by_id or target_id not in nodes_by_id:
                message = "Workflow contains edge with missing node reference"
                raise ExecutionGraphValidationError(message=message)

            outbound[source_id].append(target_id)
            inbound[target_id].append(source_id)
            indegree[target_id] += 1

        topological_order = self._topological_order(
            indegree=indegree,
            outbound=outbound,
        )
        input_node_id = input_nodes[0].id
        output_node_id = output_nodes[0].id
        self._validate_connectivity(
            input_node_id=input_node_id,
            output_node_id=output_node_id,
            outbound=outbound,
            inbound=inbound,
            nodes_by_id=nodes_by_id,
        )

        return {
            "input_node_id": input_node_id,
            "output_node_id": output_node_id,
            "nodes_by_id": nodes_by_id,
            "outbound": outbound,
            "inbound": inbound,
            "topological_order": topological_order,
        }

    def _topological_order(
        self,
        indegree: dict[int, int],
        outbound: dict[int, list[int]],
    ) -> list[int]:
        """Build topological order for workflow nodes.

        Args:
            indegree: Incoming edge count by node.
            outbound: Outbound adjacency map.

        Returns:
            Ordered node IDs.

        Raises:
            ExecutionGraphValidationError: If graph has a cycle.

        """
        queue: deque[int] = deque(
            node_id for node_id, node_indegree in indegree.items() if node_indegree == 0
        )
        order: list[int] = []
        seen_indegree = dict(indegree)
        while queue:
            node_id = queue.popleft()
            order.append(node_id)
            for target_id in outbound[node_id]:
                seen_indegree[target_id] -= 1
                if seen_indegree[target_id] == 0:
                    queue.append(target_id)

        if len(order) != len(indegree):
            message = "Workflow graph must be acyclic"
            raise ExecutionGraphValidationError(message=message)

        return order

    def _validate_connectivity(
        self,
        input_node_id: int,
        output_node_id: int,
        outbound: dict[int, list[int]],
        inbound: dict[int, list[int]],
        nodes_by_id: dict[int, Node],
    ) -> None:
        """Validate that every node is on a path from input to output.

        Args:
            input_node_id: Input node ID.
            output_node_id: Output node ID.
            outbound: Outbound adjacency map.
            inbound: Inbound adjacency map.
            nodes_by_id: Workflow nodes by ID.

        Raises:
            ExecutionGraphValidationError: If graph contains disconnected nodes.

        """
        reachable_from_input = self._collect_reachable(
            start_node_id=input_node_id,
            adjacency=outbound,
        )
        reaches_output = self._collect_reachable(
            start_node_id=output_node_id,
            adjacency=inbound,
        )
        for node_id in nodes_by_id:
            if node_id not in reachable_from_input or node_id not in reaches_output:
                message = "All workflow nodes must belong to input->output path"
                raise ExecutionGraphValidationError(message=message)

    def _collect_reachable(
        self,
        start_node_id: int,
        adjacency: dict[int, list[int]],
    ) -> set[int]:
        """Collect reachable nodes using DFS.

        Args:
            start_node_id: Start node ID.
            adjacency: Adjacency map.

        Returns:
            Set of reachable node IDs.

        """
        stack = [start_node_id]
        visited: set[int] = set()
        while stack:
            node_id = stack.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            stack.extend(adjacency[node_id])
        return visited

    def _extract_input_value(self, input_data: dict | None) -> str:
        """Extract text input for input node execution.

        Args:
            input_data: Execution input payload.

        Returns:
            Input value.

        Raises:
            ExecutionInputValidationError: If payload is invalid.

        """
        if input_data is None:
            message = "Execution input payload is required"
            raise ExecutionInputValidationError(message=message)

        value = input_data.get("value")
        if not isinstance(value, str):
            message = "Execution input_data.value must be a string"
            raise ExecutionInputValidationError(message=message)

        return value

    async def _execute_llm_node(
        self,
        session: AsyncSession,
        workflow_owner_id: int,
        node_data: dict[str, object],
        parent_values: list[str],
    ) -> str:
        """Run one LLM node.

        Args:
            session: Database session.
            workflow_owner_id: Workflow owner ID.
            node_data: Persisted node data.
            parent_values: Upstream values.

        Returns:
            LLM output text.

        Raises:
            ExecutionGraphValidationError: If node configuration is invalid.

        """
        llm_provider_id = node_data.get("llm_provider_id")
        if not isinstance(llm_provider_id, int) or llm_provider_id <= 0:
            message = "LLM node requires a valid llm_provider_id"
            raise ExecutionGraphValidationError(message=message)

        model = node_data.get("model")
        if not isinstance(model, str) or not model:
            message = "LLM node requires a non-empty model"
            raise ExecutionGraphValidationError(message=message)

        system_prompt_value = node_data.get("system_prompt", "")
        if not isinstance(system_prompt_value, str):
            message = "LLM node field system_prompt must be a string"
            raise ExecutionGraphValidationError(message=message)

        llm_provider = await self._provider_repository.get_by(
            session=session,
            id=llm_provider_id,
            user_id=workflow_owner_id,
        )
        if llm_provider is None:
            message = "Referenced LLM provider does not exist"
            raise ExecutionGraphValidationError(message=message)

        try:
            response = await self._llm_client_factory.get_client(
                llm_provider=llm_provider
            ).chat(
                model=model,
                messages=[
                    ChatMessage(role="system", content=system_prompt_value),
                    ChatMessage(role="user", content="\n".join(parent_values)),
                ],
            )
        except httpx.TimeoutException as exc:
            raise LLMProviderConnectionError(
                message="LLM provider request timed out while running execution"
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            message = f"LLM provider returned {exc.response.status_code}"
            if detail:
                message = f"{message}: {detail[:300]}"
            raise LLMProviderConnectionError(message=message) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderConnectionError from exc

        return response.message.content
