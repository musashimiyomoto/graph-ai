"""Workflow graph transfer: export, import, and duplicate.

All three share the same portable graph shape (`WorkflowGraphTransfer`) —
nodes referenced by list position rather than database ID, since a
transferred graph always creates fresh nodes. Export additionally scrubs
account-private references (LLM provider, Telegram bot) that only make sense
in the exporting account; duplicate keeps them since it stays within the
same account.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import EdgeRepository, NodeRepository, WorkflowRepository
from enums import NodeType
from exceptions import NodeDataValidationError, WorkflowNotFoundError
from nodes import build_node_catalog
from schemas import (
    EdgeCreate,
    EdgeResponse,
    NodeCatalogItem,
    NodeCreate,
    NodeFieldDataSourceKind,
    NodeResponse,
    WorkflowCreate,
    WorkflowExportResponse,
    WorkflowGraphEdge,
    WorkflowGraphNode,
    WorkflowGraphTransfer,
    WorkflowResponse,
    WorkflowTemplateResponse,
)
from templates import TEMPLATE_DEFINITIONS, get_template_definition
from usecases.edge import EdgeUsecase
from usecases.node import NodeUsecase
from usecases.workflow import WorkflowUsecase

# Datasource kinds that reference a private, per-user resource — meaningless
# (or outright wrong) once a graph leaves the exporting account. LLM_MODEL
# and VECTOR_COLLECTION are plain strings naming a model/collection, not an
# owned resource ID, so they travel with the export unchanged.
_ACCOUNT_PRIVATE_DATASOURCE_KINDS = {
    NodeFieldDataSourceKind.EMAIL_ACCOUNT,
    NodeFieldDataSourceKind.LLM_PROVIDER,
    NodeFieldDataSourceKind.TELEGRAM_BOT,
    NodeFieldDataSourceKind.POSTGRES_CONNECTION,
    NodeFieldDataSourceKind.MCP_SERVER,
    NodeFieldDataSourceKind.WORKFLOW,
}


def _scrub_account_private_fields(
    node_type: NodeType,
    data: dict[str, object],
    node_catalog: dict[NodeType, NodeCatalogItem],
) -> dict[str, object]:
    """Null out fields referencing a private per-account resource.

    Args:
        node_type: The node's type (looks up its catalog spec).
        data: The node's config data.
        node_catalog: The full node catalog (type -> spec).

    Returns:
        A copy of `data` with account-private reference fields set to None.

    """
    spec = node_catalog[node_type]
    scrubbed = dict(data)
    for field in spec.fields:
        if (
            field.datasource is not None
            and field.datasource.kind in _ACCOUNT_PRIVATE_DATASOURCE_KINDS
        ):
            scrubbed[field.name] = None
    return scrubbed


class WorkflowTransferUsecase:
    """Business logic for exporting, importing, and duplicating workflows."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._workflow_repository = WorkflowRepository()
        self._node_repository = NodeRepository()
        self._edge_repository = EdgeRepository()
        self._node_catalog = build_node_catalog()
        self._workflow_usecase = WorkflowUsecase()
        self._node_usecase = NodeUsecase()
        self._edge_usecase = EdgeUsecase()

    async def _load_graph_transfer(
        self,
        session: AsyncSession,
        workflow_id: int,
        *,
        scrub_account_private_fields: bool,
    ) -> WorkflowGraphTransfer:
        """Load a workflow's live graph in the portable transfer shape.

        Args:
            session: The session.
            workflow_id: The workflow ID (already ownership-checked by the caller).
            scrub_account_private_fields: Whether to null out LLM
                provider/Telegram bot references (export), or keep them
                (duplicate, same account).

        Returns:
            The portable graph.

        """
        nodes = [
            NodeResponse.model_validate(node)
            for node in await self._node_repository.get_all(
                session=session, workflow_id=workflow_id
            )
        ]
        edges = [
            EdgeResponse.model_validate(edge)
            for edge in await self._edge_repository.get_all(
                session=session, workflow_id=workflow_id
            )
        ]

        index_by_node_id = {node.id: index for index, node in enumerate(nodes)}

        transfer_nodes = [
            WorkflowGraphNode(
                type=node.type,
                data=(
                    _scrub_account_private_fields(
                        node.type, node.data, self._node_catalog
                    )
                    if scrub_account_private_fields
                    else node.data
                ),
                position_x=node.position_x,
                position_y=node.position_y,
                parent_index=(
                    index_by_node_id[node.parent_node_id]
                    if node.parent_node_id is not None
                    else None
                ),
            )
            for node in nodes
        ]
        transfer_edges = [
            WorkflowGraphEdge(
                source_index=index_by_node_id[edge.source_node_id],
                target_index=index_by_node_id[edge.target_node_id],
                source_handle=edge.source_handle,
                target_handle=edge.target_handle,
                coercion=edge.coercion,
            )
            for edge in edges
        ]

        return WorkflowGraphTransfer(nodes=transfer_nodes, edges=transfer_edges)

    async def export_workflow(
        self, session: AsyncSession, workflow_id: int, user_id: int
    ) -> WorkflowExportResponse:
        """Export a workflow as a portable, account-scrubbed graph.

        Args:
            session: The session.
            workflow_id: The workflow ID.
            user_id: The owner user ID.

        Returns:
            The export payload.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session, id=workflow_id, owner_id=user_id
        )
        if not workflow:
            raise WorkflowNotFoundError

        graph = await self._load_graph_transfer(
            session=session, workflow_id=workflow_id, scrub_account_private_fields=True
        )
        return WorkflowExportResponse(name=workflow.name, graph=graph)

    async def _create_workflow_from_graph(
        self,
        session: AsyncSession,
        user_id: int,
        name: str,
        graph: WorkflowGraphTransfer,
        *,
        allow_unset_references: bool,
    ) -> WorkflowResponse:
        """Create a new workflow and populate it from a portable graph.

        Args:
            session: The session.
            user_id: The owner user ID.
            name: The new workflow's name.
            graph: The portable graph to rebuild.
            allow_unset_references: See `NodeUsecase.create_node` — True for
                import/template (references don't apply to this account),
                False for duplicate (same account, references stay valid).

        Returns:
            The newly created workflow.

        Raises:
            NodeDataValidationError: If an edge or a Loop-body node's
                `parent_index` references an out-of-range (or forward/self)
                node index, or any node's data fails validation.
            LLMProviderNotFoundError: If a kept (non-scrubbed) provider
                reference doesn't belong to this account.
            TelegramBotNotFoundError: If a kept (non-scrubbed) bot reference
                doesn't belong to this account.

        """
        # Fail fast on a malformed graph (e.g. a hand-edited import file)
        # before writing anything — creation below isn't wrapped in one DB
        # transaction (each create_workflow/create_node/create_edge call
        # commits on its own), so validating indices up front avoids leaving
        # an orphaned partial workflow behind for an error that pure request
        # data already reveals.
        node_count = len(graph.nodes)
        for graph_edge in graph.edges:
            if not (0 <= graph_edge.source_index < node_count) or not (
                0 <= graph_edge.target_index < node_count
            ):
                message = (
                    f"Edge references an out-of-range node index "
                    f"(have {node_count} nodes)."
                )
                raise NodeDataValidationError(message=message)
        for index, graph_node in enumerate(graph.nodes):
            # A parent must already exist by the time its body node is
            # created (see the loop below), so it must appear strictly
            # earlier in the list — same invariant export relies on (a Loop
            # node's id, and so its export position, always precedes its
            # body nodes', since a body node's parent_node_id can't be set
            # to a not-yet-created node in the first place).
            if graph_node.parent_index is not None and not (
                0 <= graph_node.parent_index < index
            ):
                message = (
                    f"Node {index} references an out-of-range or forward "
                    f"parent_index (have {node_count} nodes)."
                )
                raise NodeDataValidationError(message=message)

        workflow = await self._workflow_usecase.create_workflow(
            session=session, user_id=user_id, data=WorkflowCreate(name=name)
        )

        created_node_ids: list[int] = []
        for graph_node in graph.nodes:
            created = await self._node_usecase.create_node(
                session=session,
                user_id=user_id,
                data=NodeCreate(
                    workflow_id=workflow.id,
                    type=graph_node.type,
                    data=graph_node.data,
                    position_x=graph_node.position_x,
                    position_y=graph_node.position_y,
                    parent_node_id=(
                        created_node_ids[graph_node.parent_index]
                        if graph_node.parent_index is not None
                        else None
                    ),
                ),
                allow_unset_references=allow_unset_references,
            )
            created_node_ids.append(created.id)

        for graph_edge in graph.edges:
            await self._edge_usecase.create_edge(
                session=session,
                user_id=user_id,
                data=EdgeCreate(
                    workflow_id=workflow.id,
                    source_node_id=created_node_ids[graph_edge.source_index],
                    target_node_id=created_node_ids[graph_edge.target_index],
                    source_handle=graph_edge.source_handle,
                    target_handle=graph_edge.target_handle,
                    coercion=graph_edge.coercion,
                ),
            )

        return workflow

    async def import_workflow(
        self,
        session: AsyncSession,
        user_id: int,
        name: str,
        graph: WorkflowGraphTransfer,
    ) -> WorkflowResponse:
        """Create a new workflow from an imported (or templated) graph.

        Args:
            session: The session.
            user_id: The owner user ID.
            name: The new workflow's name.
            graph: The portable graph, as produced by `export_workflow` or a
                template definition.

        Returns:
            The newly created workflow.

        """
        return await self._create_workflow_from_graph(
            session=session,
            user_id=user_id,
            name=name,
            graph=graph,
            allow_unset_references=True,
        )

    async def duplicate_workflow(
        self, session: AsyncSession, workflow_id: int, user_id: int
    ) -> WorkflowResponse:
        """Copy a workflow within the same account, keeping its references.

        Args:
            session: The session.
            workflow_id: The workflow ID to duplicate.
            user_id: The owner user ID.

        Returns:
            The newly created duplicate workflow.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        source = await self._workflow_repository.get_by(
            session=session, id=workflow_id, owner_id=user_id
        )
        if not source:
            raise WorkflowNotFoundError

        graph = await self._load_graph_transfer(
            session=session,
            workflow_id=workflow_id,
            scrub_account_private_fields=False,
        )
        return await self._create_workflow_from_graph(
            session=session,
            user_id=user_id,
            name=f"{source.name} (copy)",
            graph=graph,
            allow_unset_references=False,
        )

    def list_templates(self) -> list[WorkflowTemplateResponse]:
        """List the global workflow template catalog.

        Returns:
            Template metadata (no graph — kept out of the list response).

        """
        return [
            WorkflowTemplateResponse(
                key=definition.key,
                name=definition.name,
                description=definition.description,
                category=definition.category,
                setup_steps=list(definition.setup_steps),
                settings_sections=list(definition.settings_sections),
                node_count=len(definition.graph.nodes),
            )
            for definition in TEMPLATE_DEFINITIONS
        ]

    async def instantiate_template(
        self,
        session: AsyncSession,
        user_id: int,
        key: str,
        name: str | None,
    ) -> WorkflowResponse:
        """Create a new workflow from a global template's graph.

        Args:
            session: The session.
            user_id: The owner user ID.
            key: The template's stable identifier.
            name: Name for the new workflow; defaults to the template's name.

        Returns:
            The newly created workflow.

        Raises:
            WorkflowTemplateNotFoundError: If the template key is unregistered.

        """
        definition = get_template_definition(key)
        return await self._create_workflow_from_graph(
            session=session,
            user_id=user_id,
            name=name or definition.name,
            graph=definition.graph,
            allow_unset_references=True,
        )
