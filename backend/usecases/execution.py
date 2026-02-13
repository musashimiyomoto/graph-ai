"""Execution use case implementation."""

from collections import deque
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import (
    EdgeRepository,
    ExecutionRepository,
    LLMProviderRepository,
    NodeRepository,
    WorkflowRepository,
)
from enums import ExecutionStatus, NodeType
from exceptions import (
    BaseError,
    ExecutionGraphValidationError,
    ExecutionInputValidationError,
    ExecutionNotFoundError,
    WorkflowNotFoundError,
)
from nodes import NodeExecutionContext, NodeHandlerRegistry
from schemas import (
    EdgeResponse,
    ExecutionCreate,
    ExecutionGraphContext,
    ExecutionOutputPayload,
    ExecutionResponse,
    NodeResponse,
)


class ExecutionUsecase:
    """Execution business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._execution_repository = ExecutionRepository()
        self._workflow_repository = WorkflowRepository()
        self._node_repository = NodeRepository()
        self._edge_repository = EdgeRepository()
        self._llm_provider_repository = LLMProviderRepository()
        self._node_registry = NodeHandlerRegistry(
            llm_provider_repository=self._llm_provider_repository
        )

    async def create_execution(
        self,
        session: AsyncSession,
        user_id: int,
        data: ExecutionCreate,
    ) -> ExecutionResponse:
        """Create and execute a workflow execution synchronously.

        Args:
            session: The session.
            user_id: The owner user ID.
            data: The execution payload.

        Returns:
            The created execution.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.
            ExecutionGraphValidationError: If graph is invalid for execution.
            ExecutionInputValidationError: If input payload is invalid.

        """
        workflow = await self._workflow_repository.get_by(
            session=session,
            id=data.workflow_id,
            owner_id=user_id,
        )
        if not workflow:
            raise WorkflowNotFoundError

        graph = self._build_graph_context(
            nodes=[
                NodeResponse.model_validate(node)
                for node in await self._node_repository.get_all(
                    session=session,
                    workflow_id=data.workflow_id,
                )
            ],
            edges=[
                EdgeResponse.model_validate(edge)
                for edge in await self._edge_repository.get_all(
                    session=session,
                    workflow_id=data.workflow_id,
                )
            ],
        )

        execution = await self._execution_repository.create(
            session=session,
            data={
                "workflow_id": data.workflow_id,
                "input_data": data.input_data.model_dump(),
                "status": ExecutionStatus.RUNNING,
            },
        )

        try:
            output_data = await self._run_execution(
                session=session, execution_id=execution.id, graph=graph
            )
        except BaseError as exc:
            await self._mark_execution_failed(
                session=session, execution_id=execution.id, error=exc.message
            )
        else:
            await self._mark_execution_success(
                session=session, execution_id=execution.id, output_data=output_data
            )

        return await self.get_execution(
            session=session, execution_id=execution.id, user_id=user_id
        )

    async def get_executions(
        self, session: AsyncSession, user_id: int, workflow_id: int
    ) -> list[ExecutionResponse]:
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

        return [
            ExecutionResponse.model_validate(execution)
            for execution in await self._execution_repository.get_all(
                session=session, workflow_id=workflow_id
            )
        ]

    async def get_execution(
        self, session: AsyncSession, execution_id: int, user_id: int
    ) -> ExecutionResponse:
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

        return ExecutionResponse.model_validate(execution)

    async def _run_execution(
        self, session: AsyncSession, execution_id: int, graph: ExecutionGraphContext
    ) -> ExecutionOutputPayload:
        """Execute workflow nodes for an execution and return output payload.

        Args:
            session: Database session.
            execution_id: Execution ID.
            graph: Validated graph context.

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

        input_value = self._extract_input_value(input_data=execution.input_data)
        outputs_by_node: dict[int, str] = {}
        for node_id in graph.topological_order:
            node = graph.nodes_by_id[node_id]
            parent_values = [
                outputs_by_node[parent_id] for parent_id in graph.inbound[node_id]
            ]
            if node.type is not NodeType.INPUT and not parent_values:
                message = f"Node {node.id} does not have input value"
                raise ExecutionGraphValidationError(message=message)

            outputs_by_node[node_id] = await self._node_registry.execute(
                node_type=node.type,
                context=NodeExecutionContext(
                    session=session,
                    workflow_owner_id=workflow.owner_id,
                    node_data=node.data,
                    parent_values=parent_values,
                    input_value=input_value,
                ),
            )

        return ExecutionOutputPayload(value=outputs_by_node[graph.output_node_id])

    async def _mark_execution_success(
        self,
        session: AsyncSession,
        execution_id: int,
        output_data: ExecutionOutputPayload,
    ) -> ExecutionResponse:
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
                "output_data": output_data.model_dump(),
                "error": None,
                "finished_at": datetime.now(tz=UTC).replace(tzinfo=None),
            },
        )
        if updated_execution is None:
            raise ExecutionNotFoundError

        return ExecutionResponse.model_validate(updated_execution)

    async def _mark_execution_failed(
        self,
        session: AsyncSession,
        execution_id: int,
        error: str,
    ) -> ExecutionResponse:
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

        return ExecutionResponse.model_validate(updated_execution)

    def _build_graph_context(
        self, nodes: list[NodeResponse], edges: list[EdgeResponse]
    ) -> ExecutionGraphContext:
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
            indegree=indegree, outbound=outbound
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

        return ExecutionGraphContext(
            input_node_id=input_node_id,
            output_node_id=output_node_id,
            nodes_by_id=nodes_by_id,
            outbound=outbound,
            inbound=inbound,
            topological_order=topological_order,
        )

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
        nodes_by_id: dict[int, NodeResponse],
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
        for node_id in nodes_by_id:
            if node_id not in self._collect_reachable(
                start_node_id=input_node_id, adjacency=outbound
            ) or node_id not in self._collect_reachable(
                start_node_id=output_node_id, adjacency=inbound
            ):
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
