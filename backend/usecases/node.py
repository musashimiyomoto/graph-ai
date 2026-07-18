"""Node use case implementation."""

import json
from typing import Any
from urllib.parse import urlparse

from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import (
    EmailAccountRepository,
    LLMProviderRepository,
    NodeRepository,
    NodeScheduleRepository,
    PostgresConnectionRepository,
    TelegramBotRepository,
    WorkflowRepository,
)
from enums import InputNodeFormat, NodeType, ValidatorType
from exceptions import (
    EmailAccountNotFoundError,
    LLMProviderNotFoundError,
    NodeDataValidationError,
    NodeNotFoundError,
    PostgresConnectionNotFoundError,
    TelegramBotNotFoundError,
    WorkflowNotFoundError,
)
from nodes import build_node_catalog
from schemas import (
    NodeCatalogItem,
    NodeCatalogItemResponse,
    NodeCreate,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeResponse,
    NodeUpdate,
)


def _field_is_visible(field: NodeFieldSpec, data: dict[str, Any]) -> bool:
    """Mirror the frontend's declarative `visible_when` check.

    A field hidden by its `visible_when` rule (e.g. a Telegram bot picker
    when `format != telegram`) may still carry a leftover/placeholder value
    in `data` — it must not be reference-checked, or a value that only makes
    sense while the field is visible (or a stale default) would wrongly fail
    validation for a node where that field is irrelevant.
    """
    rule = field.visible_when
    if rule is None:
        return True
    controlling_value = data.get(rule.field)
    if rule.equals is not None:
        return controlling_value == rule.equals
    return controlling_value != rule.not_equals


class NodeUsecase:
    """Node business logic."""

    def __init__(self) -> None:
        """Initialize the usecase."""
        self._node_repository = NodeRepository()
        self._workflow_repository = WorkflowRepository()
        self._llm_provider_repository = LLMProviderRepository()
        self._telegram_bot_repository = TelegramBotRepository()
        self._email_account_repository = EmailAccountRepository()
        self._node_schedule_repository = NodeScheduleRepository()
        self._postgres_connection_repository = PostgresConnectionRepository()
        self._node_catalog = build_node_catalog()

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
        allow_unset_references: bool = False,
    ) -> None:
        """Validate one node field.

        Args:
            field: Field schema.
            value: Field value.
            errors: Error collector.
            allow_unset_references: When True, a required datasource field
                that references another user's private resource (provider,
                bot) — or is only meaningful once one of those is chosen
                (LLM_MODEL, which depends on a provider) — is allowed to be
                `None` even though it's normally required. Used only when
                rebuilding a node from a transferred graph (import/
                duplicate/template) whose reference IDs were scrubbed or
                don't apply to the target account — the user fills them back
                in via the node inspector, same as an existing node whose
                provider/bot was since deleted.

        """
        if value is None and (
            not field.required
            or (
                allow_unset_references
                and field.datasource is not None
                and field.datasource.kind
                in {
                    NodeFieldDataSourceKind.LLM_PROVIDER,
                    NodeFieldDataSourceKind.TELEGRAM_BOT,
                    NodeFieldDataSourceKind.EMAIL_ACCOUNT,
                    NodeFieldDataSourceKind.LLM_MODEL,
                    NodeFieldDataSourceKind.POSTGRES_CONNECTION,
                }
            )
        ):
            return

        validators = field.validators

        self._validate_min_length_field(field=field, value=value, errors=errors)
        self._validate_select_field(field=field, value=value, errors=errors)
        self._validate_ge_field(field=field, value=value, errors=errors)
        self._validate_le_field(field=field, value=value, errors=errors)

        if ValidatorType.JSON.value in validators:
            self._validate_json_field(field=field, value=value, errors=errors)

        if ValidatorType.CRON.value in validators:
            self._validate_cron_field(field=field, value=value, errors=errors)

        if ValidatorType.URL.value in validators:
            self._validate_url_field(field=field, value=value, errors=errors)

    def _validate_min_length_field(
        self,
        *,
        field: NodeFieldSpec,
        value: object,
        errors: list[str],
    ) -> None:
        """Append an error if a string value is shorter than the minimum."""
        if ValidatorType.MIN_LENGTH.value not in field.validators:
            return
        min_length = field.validators[ValidatorType.MIN_LENGTH.value]
        if not isinstance(value, str) or len(value) < int(min_length):
            errors.append(
                f"Field '{field.name}' must be a string with min length {min_length}"
            )

    def _validate_select_field(
        self,
        *,
        field: NodeFieldSpec,
        value: object,
        errors: list[str],
    ) -> None:
        """Append an error if a value isn't one of the allowed options."""
        if ValidatorType.SELECT.value not in field.validators:
            return
        allowed = field.validators[ValidatorType.SELECT.value]
        if value not in allowed:
            options = ", ".join(str(option) for option in allowed)
            errors.append(f"Field '{field.name}' must be one of: {options}")

    def _validate_ge_field(
        self,
        *,
        field: NodeFieldSpec,
        value: object,
        errors: list[str],
    ) -> None:
        """Append an error if a numeric value is below the minimum."""
        if ValidatorType.GE.value not in field.validators:
            return
        threshold = float(field.validators[ValidatorType.GE.value])
        if not isinstance(value, int | float) or value < threshold:
            errors.append(f"Field '{field.name}' must be >= {threshold}")

    def _validate_le_field(
        self,
        *,
        field: NodeFieldSpec,
        value: object,
        errors: list[str],
    ) -> None:
        """Append an error if a numeric value exceeds the maximum."""
        if ValidatorType.LE.value not in field.validators:
            return
        threshold = float(field.validators[ValidatorType.LE.value])
        if not isinstance(value, int | float) or value > threshold:
            errors.append(f"Field '{field.name}' must be <= {threshold}")

    def _validate_json_field(
        self,
        *,
        field: NodeFieldSpec,
        value: object,
        errors: list[str],
    ) -> None:
        """Append an error if a non-empty string value isn't valid JSON."""
        if not isinstance(value, str) or not value.strip():
            return
        try:
            json.loads(value)
        except json.JSONDecodeError:
            errors.append(f"Field '{field.name}' must be valid JSON")

    def _validate_cron_field(
        self,
        *,
        field: NodeFieldSpec,
        value: object,
        errors: list[str],
    ) -> None:
        """Append an error if a non-empty string value isn't a valid cron expression."""
        if not isinstance(value, str) or not value.strip():
            return
        if not croniter.is_valid(value):
            errors.append(f"Field '{field.name}' must be a valid cron expression")

    def _validate_url_field(
        self,
        *,
        field: NodeFieldSpec,
        value: object,
        errors: list[str],
    ) -> None:
        """Append an error unless a value is an absolute HTTP(S) URL."""
        if not isinstance(value, str):
            errors.append(f"Field '{field.name}' must be an absolute http(s) URL")
            return
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"Field '{field.name}' must be an absolute http(s) URL")

    def _validate_node_data(
        self,
        node_type: NodeType,
        data: dict[str, Any],
        *,
        allow_unset_references: bool = False,
    ) -> dict[str, Any]:
        """Validate node payload against catalog schema.

        Args:
            node_type: Node type.
            data: Incoming node data.
            allow_unset_references: See `_validate_node_field`. A field this
                loosens must still be *present* (as `None`) in `data` — a
                genuinely missing required field is still rejected, same as
                always.

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
            if not _field_is_visible(field, data):
                continue
            if field.required and field.name not in data:
                errors.append(f"Missing required field: '{field.name}'")
                continue

            if field.name not in data:
                continue

            self._validate_node_field(
                field=field,
                value=data[field.name],
                errors=errors,
                allow_unset_references=allow_unset_references,
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
            TelegramBotNotFoundError: If a referenced bot is not owned by the user.

        """
        spec = self._get_node_spec(node_type=node_type)

        for field in spec.fields:
            if (
                field.datasource is None
                or field.name not in data
                or data[field.name] is None
                or not _field_is_visible(field, data)
            ):
                continue

            value = data[field.name]
            if field.datasource.kind is NodeFieldDataSourceKind.LLM_PROVIDER:
                await self._validate_provider_reference(
                    session=session, user_id=user_id, field=field, value=value
                )
            elif field.datasource.kind is NodeFieldDataSourceKind.TELEGRAM_BOT:
                await self._validate_telegram_reference(
                    session=session, user_id=user_id, field=field, value=value
                )
            elif field.datasource.kind is NodeFieldDataSourceKind.EMAIL_ACCOUNT:
                await self._validate_email_reference(
                    session=session, user_id=user_id, field=field, value=value
                )
            elif field.datasource.kind is NodeFieldDataSourceKind.POSTGRES_CONNECTION:
                await self._validate_postgres_connection_reference(
                    session=session, user_id=user_id, field=field, value=value
                )

    @staticmethod
    def _reference_id(field: NodeFieldSpec, value: object, label: str) -> int:
        """Validate and return a positive external-resource ID."""
        if not isinstance(value, int) or value <= 0:
            message = f"Field '{field.name}' must be a positive integer {label} ID."
            raise NodeDataValidationError(message=message)
        return value

    async def _validate_provider_reference(
        self,
        session: AsyncSession,
        user_id: int,
        field: NodeFieldSpec,
        value: object,
    ) -> None:
        """Ensure a referenced LLM provider belongs to the user."""
        provider_id = self._reference_id(field, value, "provider")
        provider = await self._llm_provider_repository.get_by(
            session=session, id=provider_id, user_id=user_id
        )
        if provider is None:
            raise LLMProviderNotFoundError

    async def _validate_telegram_reference(
        self,
        session: AsyncSession,
        user_id: int,
        field: NodeFieldSpec,
        value: object,
    ) -> None:
        """Ensure a referenced Telegram bot belongs to the user."""
        bot_id = self._reference_id(field, value, "bot")
        bot = await self._telegram_bot_repository.get_by(
            session=session, id=bot_id, user_id=user_id
        )
        if bot is None:
            raise TelegramBotNotFoundError

    async def _validate_email_reference(
        self,
        session: AsyncSession,
        user_id: int,
        field: NodeFieldSpec,
        value: object,
    ) -> None:
        """Ensure a referenced email account belongs to the user."""
        account_id = self._reference_id(field, value, "email account")
        account = await self._email_account_repository.get_by(
            session=session, id=account_id, user_id=user_id
        )
        if account is None:
            raise EmailAccountNotFoundError

    async def _validate_postgres_connection_reference(
        self,
        session: AsyncSession,
        user_id: int,
        field: NodeFieldSpec,
        value: object,
    ) -> None:
        """Ensure a referenced PostgreSQL connection belongs to the user."""
        connection_id = self._reference_id(field, value, "PostgreSQL connection")
        connection = await self._postgres_connection_repository.get_by(
            session=session, id=connection_id, user_id=user_id
        )
        if connection is None:
            raise PostgresConnectionNotFoundError

    async def _sync_node_schedule(
        self,
        session: AsyncSession,
        node_id: int,
        node_type: NodeType,
        data: dict[str, Any],
    ) -> None:
        """Create/update/remove this node's schedule row to match its data.

        A schedule row exists iff the node is an Input node currently
        configured as `format=schedule` with a non-empty cron expression —
        switching away from `schedule`, clearing the expression, or saving a
        non-Input node all remove any existing row, so the poller never acts
        on a stale schedule left over from a since-changed configuration.
        """
        if node_type is not NodeType.INPUT:
            return

        cron_expression = data.get("cron_expression")
        is_scheduled = (
            data.get("format") == InputNodeFormat.SCHEDULE.value
            and isinstance(cron_expression, str)
            and bool(cron_expression.strip())
        )

        existing = await self._node_schedule_repository.get_by(
            session=session, node_id=node_id
        )

        if not is_scheduled:
            if existing is not None:
                await self._node_schedule_repository.delete_by(
                    session=session, node_id=node_id
                )
            return

        if existing is None:
            await self._node_schedule_repository.create(
                session=session,
                data={"node_id": node_id, "cron_expression": cron_expression},
            )
        elif existing.cron_expression != cron_expression:
            await self._node_schedule_repository.update_by(
                session=session,
                data={"cron_expression": cron_expression},
                node_id=node_id,
            )

    async def _validate_parent_scope(
        self,
        session: AsyncSession,
        workflow_id: int,
        node_type: NodeType,
        parent_node_id: int | None,
    ) -> None:
        """Validate a node's scope against its type and (if any) parent Loop.

        Enforces three invariants, the only cross-node checks in node CRUD
        (every other check is either single-node field validation or a
        cross-resource reference lookup):
        - `LOOP_INPUT`/`LOOP_OUTPUT` only make sense inside a loop body —
          reject them at the top level (`parent_node_id is None`).
        - `INPUT`/`OUTPUT` carry a top-level-only concept (Telegram/schedule
          triggers, delivery formats) that's meaningless inside a loop body —
          reject them when `parent_node_id` is set.
        - Nested loops (a `LOOP` node whose `parent_node_id` is set at all)
          are disallowed in v1 — the recursive runner's guardrails (iteration
          caps, retry-from-zero) aren't designed for nested iteration counts
          multiplying against each other.
        Every other node type may live at either scope, but `parent_node_id`
        (when set) must always reference a real `LOOP` node in this workflow.

        Args:
            session: Database session.
            workflow_id: The workflow the node belongs to (already
                ownership-checked by the caller).
            node_type: The node type being created.
            parent_node_id: The requested parent Loop node's id, or None.

        Raises:
            NodeDataValidationError: If any invariant above is violated, or
                `parent_node_id` doesn't reference a Loop node in this
                workflow.

        """
        if (
            node_type in {NodeType.INPUT, NodeType.OUTPUT}
            and parent_node_id is not None
        ):
            message = (
                f"Node type '{node_type.value}' can only be created at the "
                "top level, not inside a Loop node's body"
            )
            raise NodeDataValidationError(message=message)

        if node_type is NodeType.LOOP and parent_node_id is not None:
            message = (
                "Nested loops are not supported: a Loop node's body cannot "
                "contain another Loop node"
            )
            raise NodeDataValidationError(message=message)

        if node_type in {NodeType.LOOP_INPUT, NodeType.LOOP_OUTPUT} and (
            parent_node_id is None
        ):
            message = (
                f"Node type '{node_type.value}' can only be created inside "
                "a Loop node's body"
            )
            raise NodeDataValidationError(message=message)

        if parent_node_id is None:
            return

        parent = await self._node_repository.get_by(
            session=session, id=parent_node_id, workflow_id=workflow_id
        )
        if parent is None or parent.type is not NodeType.LOOP:
            message = "parent_node_id must reference a Loop node in this workflow"
            raise NodeDataValidationError(message=message)

    async def create_node(
        self,
        session: AsyncSession,
        user_id: int,
        data: NodeCreate,
        *,
        allow_unset_references: bool = False,
    ) -> NodeResponse:
        """Create a node within a workflow.

        Args:
            session: The session.
            user_id: The owner user ID.
            data: The node creation fields.
            allow_unset_references: See `_validate_node_field`. Internal-only
                — never set by the public API (`NodeCreate` always requires a
                real reference); the workflow-transfer usecase passes True
                when rebuilding a node from an imported/duplicated/
                templated graph whose provider/bot fields were scrubbed or
                belong to a different account.

        Returns:
            The created node.

        Raises:
            WorkflowNotFoundError: If the workflow is not found.
            LLMProviderNotFoundError: If the LLM provider is not found.
            NodeDataValidationError: If the node data, or its scope, is invalid.

        """
        workflow = await self._workflow_repository.get_by(
            session=session,
            id=data.workflow_id,
            owner_id=user_id,
        )
        if not workflow:
            raise WorkflowNotFoundError

        await self._validate_parent_scope(
            session=session,
            workflow_id=data.workflow_id,
            node_type=data.type,
            parent_node_id=data.parent_node_id,
        )

        validated_data = self._validate_node_data(
            node_type=data.type,
            data=data.data,
            allow_unset_references=allow_unset_references,
        )
        await self._validate_external_references(
            session=session,
            user_id=user_id,
            node_type=data.type,
            data=validated_data,
        )

        node = await self._node_repository.create(
            session=session,
            data={**data.model_dump(), "data": validated_data},
        )
        await self._sync_node_schedule(
            session=session,
            node_id=node.id,
            node_type=node.type,
            data=validated_data,
        )
        await session.commit()
        return NodeResponse.model_validate(node)

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

        await self._sync_node_schedule(
            session=session,
            node_id=node_id,
            node_type=node.type,
            data=validated_data,
        )
        await session.commit()
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
        await session.commit()
