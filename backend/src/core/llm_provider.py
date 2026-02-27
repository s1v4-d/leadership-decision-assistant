"""Model-agnostic LLM and embedding provider factory."""

from llama_index.core import Settings as LlamaSettings
from llama_index.core.llms import LLM
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

from backend.src.core.config import Settings

_SUPPORTED_LLM_PROVIDERS = {"openai", "anthropic"}
_SUPPORTED_EMBEDDING_PROVIDERS = {"openai"}


def create_llm(settings: Settings) -> LLM:
    """Create a LlamaIndex LLM instance based on the configured provider."""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return OpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.llm_request_timeout,
        )
    if provider == "anthropic":
        from llama_index.llms.anthropic import Anthropic

        return Anthropic(  # type: ignore[no-any-return]
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    msg = f"Unsupported LLM provider: '{provider}'. Supported: {sorted(_SUPPORTED_LLM_PROVIDERS)}"
    raise ValueError(msg)


def create_embed_model(settings: Settings) -> OpenAIEmbedding:
    """Create a LlamaIndex embedding model based on the configured provider."""
    provider = settings.embedding_provider.lower()
    if provider == "openai":
        return OpenAIEmbedding(
            model_name=settings.embedding_model,
            api_key=settings.openai_api_key.get_secret_value(),
            dimensions=settings.embedding_dimension,
        )
    msg = f"Unsupported embedding provider: '{provider}'. Supported: {sorted(_SUPPORTED_EMBEDDING_PROVIDERS)}"
    raise ValueError(msg)


def configure_llm_settings(settings: Settings) -> None:
    """Set global LlamaIndex Settings.llm and Settings.embed_model."""
    LlamaSettings.llm = create_llm(settings)
    LlamaSettings.embed_model = create_embed_model(settings)
