"""LLM provider dependency providers."""

from usecases import LLMProviderUsecase


def get_llm_provider_usecase() -> LLMProviderUsecase:
    """Get the LLM provider usecase.

    Returns:
        The LLM provider usecase.

    """
    return LLMProviderUsecase()
