"""LLM node dependency providers."""

from usecases import LLMNodeUsecase


def get_llm_node_usecase() -> LLMNodeUsecase:
    """Get the LLM node usecase.

    Returns:
        The LLM node usecase.

    """
    return LLMNodeUsecase()
