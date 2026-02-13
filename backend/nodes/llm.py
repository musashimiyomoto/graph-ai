"""LLM node handler."""

import httpx

from db.repositories import LLMProviderRepository
from exceptions import ExecutionGraphValidationError, LLMProviderConnectionError
from llm import create_llm_client
from nodes.base import NodeExecutionContext
from schemas import ChatMessage, LLMProviderResponse


class LLMNodeHandler:
    """Handler for LLM nodes."""

    def __init__(self, llm_provider_repository: LLMProviderRepository) -> None:
        """Initialize handler dependencies.

        Args:
            llm_provider_repository: Repository for LLM provider lookups.

        """
        self._llm_provider_repository = llm_provider_repository

    async def execute(self, context: NodeExecutionContext) -> str:
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

        llm_provider = await self._llm_provider_repository.get_by(
            session=context.session,
            id=llm_provider_id,
            user_id=context.workflow_owner_id,
        )
        if llm_provider is None:
            message = "Referenced LLM provider does not exist"
            raise ExecutionGraphValidationError(message=message)

        try:
            response = await create_llm_client(
                llm_provider=LLMProviderResponse.model_validate(llm_provider)
            ).chat(
                model=model,
                messages=[
                    ChatMessage(role="system", content=system_prompt_value),
                    ChatMessage(role="user", content="\n".join(context.parent_values)),
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
