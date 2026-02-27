"""Tests for the model-agnostic LLM and embedding provider factory."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from backend.src.core.config import Settings
from backend.src.core.llm_provider import (
    configure_llm_settings,
    create_embed_model,
    create_llm,
)


def _make_settings(**overrides: object) -> Settings:
    defaults = {
        "_env_file": None,
        "openai_api_key": SecretStr("sk-test-key"),
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestCreateLLM:
    """Tests for the create_llm factory function."""

    @patch("backend.src.core.llm_provider.OpenAI")
    def test_create_llm_with_openai_provider(self, mock_openai_cls: MagicMock) -> None:
        mock_openai_cls.return_value = MagicMock()
        settings = _make_settings()
        llm = create_llm(settings)
        mock_openai_cls.assert_called_once_with(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.llm_request_timeout,
        )
        assert llm is mock_openai_cls.return_value

    def test_create_llm_with_anthropic_provider(self) -> None:
        mock_anthropic_cls = MagicMock()
        mock_anthropic_cls.return_value = MagicMock()
        fake_module = types.ModuleType("llama_index.llms.anthropic")
        fake_module.Anthropic = mock_anthropic_cls  # type: ignore[attr-defined]
        settings = _make_settings(llm_provider="anthropic")
        with patch.dict(sys.modules, {"llama_index.llms.anthropic": fake_module}):
            llm = create_llm(settings)
        mock_anthropic_cls.assert_called_once_with(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
        assert llm is mock_anthropic_cls.return_value

    def test_create_llm_with_unsupported_provider_raises_value_error(self) -> None:
        settings = _make_settings(llm_provider="unsupported-provider")
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm(settings)


class TestCreateEmbedModel:
    """Tests for the create_embed_model factory function."""

    @patch("backend.src.core.llm_provider.OpenAIEmbedding")
    def test_create_embed_model_with_openai_provider(self, mock_embed_cls: MagicMock) -> None:
        mock_embed_cls.return_value = MagicMock()
        settings = _make_settings()
        embed = create_embed_model(settings)
        mock_embed_cls.assert_called_once_with(
            model_name=settings.embedding_model,
            api_key=settings.openai_api_key.get_secret_value(),
            dimensions=settings.embedding_dimension,
        )
        assert embed is mock_embed_cls.return_value

    def test_create_embed_model_with_unsupported_provider_raises_value_error(self) -> None:
        settings = _make_settings(embedding_provider="unsupported-provider")
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            create_embed_model(settings)


class TestConfigureLLMSettings:
    """Tests for configure_llm_settings which sets global LlamaIndex Settings."""

    @patch("backend.src.core.llm_provider.LlamaSettings")
    @patch("backend.src.core.llm_provider.create_embed_model")
    @patch("backend.src.core.llm_provider.create_llm")
    def test_configure_llm_settings_sets_globals(
        self,
        mock_create_llm: MagicMock,
        mock_create_embed: MagicMock,
        mock_llama_settings: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_embed = MagicMock()
        mock_create_llm.return_value = mock_llm
        mock_create_embed.return_value = mock_embed

        settings = _make_settings()
        configure_llm_settings(settings)

        mock_create_llm.assert_called_once_with(settings)
        mock_create_embed.assert_called_once_with(settings)
        assert mock_llama_settings.llm == mock_llm
        assert mock_llama_settings.embed_model == mock_embed
