"""Node use case implementation."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import LLMProviderRepository, NodeRepository, WorkflowRepository
from enums import InputNodeFormat, NodeType, OutputNodeFormat, ValidatorType
from exceptions import (
    LLMProviderNotFoundError,
    NodeDataValidationError,
    NodeNotFoundError,
    WorkflowNotFoundError,
)
from schemas import (
    NodeCatalogItem,
    NodeCatalogItemResponse,
    NodeCreate,
    NodeFieldDataSource,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
    NodeResponse,
    NodeUpdate,
)


class NodeUsecase:
    """Node business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._node_repository = NodeRepository()
        self._workflow_repository = WorkflowRepository()
        self._llm_provider_repository = LLMProviderRepository()
        self._node_catalog = self._build_catalog()

    def _build_catalog(self) -> dict[NodeType, NodeCatalogItem]:
        """Build static node catalog.

        Returns:
            Mapping of node types to catalog entries.

        """
        input_fields = (
            NodeFieldSpec(
                name="label",
                required=True,
                validators={ValidatorType.MIN_LENGTH.value: 1},
                ui=NodeFieldUI(
                    widget=NodeFieldWidget.TEXT,
                    label="Label",
                    placeholder="Input label",
                ),
                default="Input node",
            ),
            NodeFieldSpec(
                name="format",
                required=True,
                validators={ValidatorType.SELECT.value: [InputNodeFormat.TXT.value]},
                ui=NodeFieldUI(widget=NodeFieldWidget.SELECT, label="Format"),
                default=InputNodeFormat.TXT.value,
            ),
        )

        llm_fields = (
            NodeFieldSpec(
                name="label",
                required=True,
                validators={ValidatorType.MIN_LENGTH.value: 1},
                ui=NodeFieldUI(
                    widget=NodeFieldWidget.TEXT,
                    label="Label",
                    placeholder="LLM label",
                ),
                default="LLM node",
            ),
            NodeFieldSpec(
                name="llm_provider_id",
                required=True,
                validators={ValidatorType.GE.value: 1},
                ui=NodeFieldUI(
                    widget=NodeFieldWidget.PROVIDER,
                    label="Provider",
                ),
                datasource=NodeFieldDataSource(
                    kind=NodeFieldDataSourceKind.LLM_PROVIDER
                ),
            ),
            NodeFieldSpec(
                name="model",
                required=True,
                validators={ValidatorType.MIN_LENGTH.value: 1},
                ui=NodeFieldUI(widget=NodeFieldWidget.MODEL, label="Model"),
                datasource=NodeFieldDataSource(
                    kind=NodeFieldDataSourceKind.LLM_MODEL,
                    depends_on="llm_provider_id",
                ),
                default="",
            ),
            NodeFieldSpec(
                name="system_prompt",
                required=True,
                validators={},
                ui=NodeFieldUI(
                    widget=NodeFieldWidget.TEXTAREA,
                    label="System prompt",
                    placeholder="You are a helpful assistant.",
                ),
                default="",
            ),
        )

        output_fields = (
            NodeFieldSpec(
                name="label",
                required=True,
                validators={ValidatorType.MIN_LENGTH.value: 1},
                ui=NodeFieldUI(
                    widget=NodeFieldWidget.TEXT,
                    label="Label",
                    placeholder="Output label",
                ),
                default="Output node",
            ),
            NodeFieldSpec(
                name="format",
                required=True,
                validators={ValidatorType.SELECT.value: [OutputNodeFormat.TXT.value]},
                ui=NodeFieldUI(widget=NodeFieldWidget.SELECT, label="Format"),
                default=OutputNodeFormat.TXT.value,
            ),
        )

        return {
            NodeType.INPUT: NodeCatalogItem(
                type=NodeType.INPUT,
                label="Input",
                icon_key="input",
                graph=NodeGraphSpec(has_input=False, has_output=True),
                fields=input_fields,
            ),
            NodeType.LLM: NodeCatalogItem(
                type=NodeType.LLM,
                label="LLM",
                icon_key="llm",
                graph=NodeGraphSpec(has_input=True, has_output=True),
                fields=llm_fields,
            ),
            NodeType.OUTPUT: NodeCatalogItem(
                type=NodeType.OUTPUT,
                label="Output",
                icon_key="output",
                graph=NodeGraphSpec(has_input=True, has_output=False),
                fields=output_fields,
            ),
        }

    def _get_node_spec(self, node_type: NodeType) -> NodeCatalogItem:
        """Return catalog entry for specific node type.

        Args:
            node_type: Node type.

        Returns:
            Node catalog item.

        """
        return self._node_catalog[node_type]

    def _validate_node_field(
        self,
        *,
        field: NodeFieldSpec,
        value: object,
        errors: list[str],
    ) -> None:
        """Validate one node field.

        Args:
            field: Field schema.
            value: Field value.
            errors: Error collector.

        """
        validators = field.validators

        if ValidatorType.MIN_LENGTH.value in validators and (
            not isinstance(value, str)
            or len(value) < int(validators[ValidatorType.MIN_LENGTH.value])
        ):
            errors.append(
                f"Field '{field.name}' must be a string with "
                f"min length {validators[ValidatorType.MIN_LENGTH.value]}"
            )

        if ValidatorType.SELECT.value in validators:
            allowed = validators[ValidatorType.SELECT.value]
            if value not in allowed:
                options = ", ".join(str(option) for option in allowed)
                errors.append(f"Field '{field.name}' must be one of: {options}")

        if ValidatorType.GE.value in validators:
            threshold = float(validators[ValidatorType.GE.value])
            if not isinstance(value, int | float) or value < threshold:
                errors.append(f"Field '{field.name}' must be >= {threshold}")

        if ValidatorType.LE.value in validators:
            threshold = float(validators[ValidatorType.LE.value])
            if not isinstance(value, int | float) or value > threshold:
                errors.append(f"Field '{field.name}' must be <= {threshold}")

    def _validate_node_data(
        self,
        node_type: NodeType,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate node payload against catalog schema.

        Args:
            node_type: Node type.
            data: Incoming node data.

        Returns:
            Validated node data.

        Raises:
            NodeDataValidationError: If payload is invalid.

        """
        spec = self._get_node_spec(node_type=node_type)
        errors: list[str] = []
        fields_by_name = {field.name: field for field in spec.fields}

        unexpected = set(data.keys()) - set(fields_by_name.keys())
        if unexpected:
            errors.append(f"Unexpected fields: {', '.join(sorted(unexpected))}")

        for field in spec.fields:
            if field.required and field.name not in data:
                errors.append(f"Missing required field: '{field.name}'")
                continue

            if field.name not in data:
                continue

            self._validate_node_field(
                field=field,
                value=data[field.name],
                errors=errors,
            )

        if errors:
            raise NodeDataValidationError(message="; ".join(errors))

        return data

    def get_node_catalog(self) -> list[NodeCatalogItemResponse]:
        """Return catalog metadata for all node types.

        Returns:
            Node catalog entries.

        """
        return [
            NodeCatalogItemResponse.model_validate(self._node_catalog[node_type])
            for node_type in NodeType
        ]

    async def _validate_external_references(
        self,
        session: AsyncSession,
        user_id: int,
        node_type: NodeType,
        data: dict[str, Any],
    ) -> None:
        """Validate cross-resource references required by node data.

        Args:
            session: Database session.
            user_id: Owner user ID.
            node_type: Type of node being validated.
            data: Validated node data payload.

        Raises:
            NodeDataValidationError: If reference format is invalid.
            LLMProviderNotFoundError: If a referenced provider is not owned by user.

        """
        spec = self._get_node_spec(node_type=node_type)

        for field in spec.fields:
            if field.datasource is None or field.name not in data:
                continue

            if field.datasource.kind is NodeFieldDataSourceKind.LLM_PROVIDER:
                provider_id = data[field.name]
                if not isinstance(provider_id, int) or provider_id <= 0:
                    raise NodeDataValidationError(
                        message=(
                            f"Field '{field.name}' must be a positive integer "
                            "provider ID."
                        )
                    )

                provider = await self._llm_provider_repository.get_by(
                    session=session,
                    id=provider_id,
                    user_id=user_id,
                )
                if not provider:
                    raise LLMProviderNotFoundError

    async def create_node(
        self,
        session: AsyncSession,
        user_id: int,
        data: NodeCreate,
    ) -> NodeResponse:
        """Create a node within a workflow.

        Args:
            session: The session.
            user_id: The owner user ID.
            data: The node creation fields.

        Returns:
            The created node.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.
            LLMProviderNotFoundError: If the LLM provider is not found.
            NodeDataValidationError: If the node data is invalid.

        """
        workflow = await self._workflow_repository.get_by(
            session=session,
            id=data.workflow_id,
            owner_id=user_id,
        )
        if not workflow:
            raise WorkflowNotFoundError

        validated_data = self._validate_node_data(node_type=data.type, data=data.data)
        await self._validate_external_references(
            session=session,
            user_id=user_id,
            node_type=data.type,
            data=validated_data,
        )

        return NodeResponse.model_validate(
            await self._node_repository.create(
                session=session,
                data={**data.model_dump(), "data": validated_data},
            )
        )

    async def get_nodes(
        self,
        session: AsyncSession,
        user_id: int,
        workflow_id: int,
    ) -> list[NodeResponse]:
        """List nodes for a workflow.

        Args:
            session: The session.
            user_id: The owner user ID.
            workflow_id: The workflow ID.

        Returns:
            The list of nodes.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.

        """
        workflow = await self._workflow_repository.get_by(
            session=session,
            id=workflow_id,
            owner_id=user_id,
        )
        if not workflow:
            raise WorkflowNotFoundError

        return [
            NodeResponse.model_validate(node)
            for node in await self._node_repository.get_all(
                session=session,
                workflow_id=workflow_id,
            )
        ]

    async def get_node(
        self,
        session: AsyncSession,
        node_id: int,
        user_id: int,
    ) -> NodeResponse:
        """Fetch a node by ID.

        Args:
            session: The session.
            node_id: The node ID.
            user_id: The owner user ID.

        Returns:
            The node.

        Raises:
            NodeNotFoundError: If the node is not found.
            WorkflowNotFoundError: If the workflow is not found.

        """
        node = await self._node_repository.get_by(session=session, id=node_id)
        if not node:
            raise NodeNotFoundError

        workflow = await self._workflow_repository.get_by(
            session=session,
            id=node.workflow_id,
            owner_id=user_id,
        )
        if not workflow:
            raise WorkflowNotFoundError

        return NodeResponse.model_validate(node)

    async def update_node(
        self,
        session: AsyncSession,
        node_id: int,
        user_id: int,
        data: NodeUpdate,
    ) -> NodeResponse:
        """Update a node by ID.

        Args:
            session: The session.
            node_id: The node ID.
            user_id: The owner user ID.
            data: The fields to update.

        Returns:
            The updated node.

        Raises:
            NodeNotFoundError: If the node is not found.
            WorkflowNotFoundError: If the workflow is not found.
            NodeDataValidationError: If node data is invalid.

        """
        node = await self.get_node(session=session, node_id=node_id, user_id=user_id)

        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            return node

        incoming_data = update_data.get("data", {})
        if not isinstance(incoming_data, dict):
            raise NodeDataValidationError(message="Node data must be an object.")

        validated_data = self._validate_node_data(
            node_type=node.type,
            data=node.data | incoming_data,
        )
        await self._validate_external_references(
            session=session,
            user_id=user_id,
            node_type=node.type,
            data=validated_data,
        )
        update_data["data"] = validated_data

        updated = await self._node_repository.update_by(
            session=session,
            data=update_data,
            id=node_id,
        )
        if not updated:
            raise NodeNotFoundError

        return NodeResponse.model_validate(updated)

    async def delete_node(
        self,
        session: AsyncSession,
        node_id: int,
        user_id: int,
    ) -> None:
        """Delete a node by ID.

        Args:
            session: The session.
            node_id: The node ID.
            user_id: The owner user ID.

        Raises:
            NodeNotFoundError: If the node is not found.
            WorkflowNotFoundError: If the workflow is not found.

        """
        await self.get_node(session=session, node_id=node_id, user_id=user_id)

        deleted = await self._node_repository.delete_by(session=session, id=node_id)
        if not deleted:
            raise NodeNotFoundError
