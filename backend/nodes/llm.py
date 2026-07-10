"""LLM node handler."""

from pydantic import ValidationError

from db.repositories import LLMProviderRepository
from enums import NodeType, PortType, ValidatorType
from exceptions import ExecutionGraphValidationError
from llm import create_llm_client
from nodes.base import NodeExecutionContext, NodeExecutionResult
from nodes.definition import NodeDefinition, NodeHandlerDeps
from schemas import (
    ChatMessage,
    GenerationParams,
    LLMProviderResponse,
    NodeFieldDataSource,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
)
from utils.encryption import decrypt
from utils.network import blocked_url_reason

_GENERATION_PARAM_FIELDS = ("temperature", "max_tokens", "top_p")


def _build_generation_params(
    node_data: dict[str, object],
) -> GenerationParams | None:
    """Build generation params from node data.

    Args:
        node_data: Raw node configuration.

    Returns:
        Parsed generation params, or None when none are configured.

    Raises:
        ExecutionGraphValidationError: If a configured value is invalid.

    """
    provided = {
        field: node_data[field]
        for field in _GENERATION_PARAM_FIELDS
        if node_data.get(field) is not None
    }
    if not provided:
        return None

    try:
        return GenerationParams.model_validate(provided)
    except ValidationError as exc:
        message = "LLM node has invalid generation parameters"
        raise ExecutionGraphValidationError(message=message) from exc


class LLMNodeHandler:
    """Handler for LLM nodes."""

    def __init__(self, llm_provider_repository: LLMProviderRepository) -> None:
        """Initialize handler dependencies.

        Args:
            llm_provider_repository: Repository for LLM provider lookups.

        """
        self._llm_provider_repository = llm_provider_repository

    async def execute(self, context: NodeExecutionContext) -> NodeExecutionResult:
        """Run one LLM node.

        Args:
            context: Node execution context.

        Returns:
            LLM output text.

        Raises:
            ExecutionGraphValidationError: If node configuration is invalid.

        """
        llm_provider_id = context.node_data.get("llm_provider_id")
        if not isinstance(llm_provider_id, int) or llm_provider_id <= 0:
            message = "LLM node requires a valid llm_provider_id"
            raise ExecutionGraphValidationError(message=message)

        model = context.node_data.get("model")
        if not isinstance(model, str) or not model:
            message = "LLM node requires a non-empty model"
            raise ExecutionGraphValidationError(message=message)

        system_prompt_value = context.node_data.get("system_prompt", "")
        if not isinstance(system_prompt_value, str):
            message = "LLM node field system_prompt must be a string"
            raise ExecutionGraphValidationError(message=message)

        params = _build_generation_params(context.node_data)

        llm_provider = await self._llm_provider_repository.get_by(
            session=context.session,
            id=llm_provider_id,
            user_id=context.workflow_owner_id,
        )
        if llm_provider is None:
            message = "Referenced LLM provider does not exist"
            raise ExecutionGraphValidationError(message=message)

        block_reason = await blocked_url_reason(
            llm_provider.base_url, allow_private=True
        )
        if block_reason is not None:
            raise ExecutionGraphValidationError(message=block_reason)

        api_key = decrypt(llm_provider.api_key) if llm_provider.api_key else None
        client = create_llm_client(
            llm_provider=LLMProviderResponse.model_validate(llm_provider),
            api_key=api_key,
        )
        messages = [
            ChatMessage(role="system", content=system_prompt_value),
            ChatMessage(role="user", content="\n".join(context.parent_values)),
        ]

        if context.on_token is None:
            response = await client.chat(model=model, messages=messages, params=params)
            return NodeExecutionResult(output=response.message.content)

        chunks: list[str] = []
        async for delta in client.stream_chat(
            model=model, messages=messages, params=params
        ):
            chunks.append(delta)
            await context.on_token(delta)

        return NodeExecutionResult(output="".join(chunks))


def _build_handler(deps: NodeHandlerDeps) -> LLMNodeHandler:
    """Build an LLM node handler from shared dependencies."""
    return LLMNodeHandler(llm_provider_repository=deps.llm_provider_repository)


DEFINITION = NodeDefinition(
    type=NodeType.LLM,
    label="LLM",
    icon_key="llm",
    graph=NodeGraphSpec(
        has_input=True,
        has_output=True,
        input_port=PortType.TEXT,
        output_port=PortType.TEXT,
    ),
    fields=(
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
            datasource=NodeFieldDataSource(kind=NodeFieldDataSourceKind.LLM_PROVIDER),
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
            # min_length=0: no minimum, but still enforces the value is a
            # string (matching the handler's own run-time type check) — an
            # empty system prompt is allowed, a non-string one isn't.
            validators={ValidatorType.MIN_LENGTH.value: 0},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXTAREA,
                label="System prompt",
                placeholder="You are a helpful assistant.",
            ),
            default="",
        ),
        NodeFieldSpec(
            name="temperature",
            required=False,
            validators={
                ValidatorType.GE.value: 0,
                ValidatorType.LE.value: 2,
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.OPTIONAL_NUMBER,
                label="Temperature",
                help="Sampling temperature. Leave blank for the provider default.",
            ),
        ),
        NodeFieldSpec(
            name="max_tokens",
            required=False,
            validators={ValidatorType.GE.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.OPTIONAL_NUMBER,
                label="Max tokens",
                help="Maximum tokens to generate. Leave blank for the default.",
                step=1,
            ),
        ),
        NodeFieldSpec(
            name="top_p",
            required=False,
            validators={
                ValidatorType.GE.value: 0,
                ValidatorType.LE.value: 1,
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.OPTIONAL_NUMBER,
                label="Top P",
                help="Nucleus sampling probability. Leave blank for the default.",
            ),
        ),
    ),
    build_handler=_build_handler,
)
