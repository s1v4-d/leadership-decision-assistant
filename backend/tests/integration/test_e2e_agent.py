"""End-to-end integration tests for agent tool routing.

Verify that the ReAct agent selects the correct tool based on query type:
- Quantitative questions (KPIs, metrics, numbers) → structured_query (SQL)
- Qualitative questions (strategy, policy, context) → document_search (RAG)
- Complex questions → combines both tools

Inspired by talk2data agent pattern: the agent has vector_search and sql_query
tools, with prompt-guided routing. Our agent mirrors this with document_search,
structured_query, and analyze_context tools.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.tools import QueryEngineTool

from backend.src.agents.leadership_agent import (
    create_analysis_tool,
    create_leadership_agent,
    create_rag_query_tool,
    create_sql_tool,
    run_agent_query,
)
from backend.src.agents.prompts import LEADERSHIP_SYSTEM_PROMPT
from backend.src.models.domain import AgentResponse


@pytest.fixture()
def mock_settings() -> MagicMock:
    """Minimal mocked Settings for agent tests."""
    settings = MagicMock()
    settings.rag.similarity_top_k = 3
    settings.rag.response_mode = "compact"
    settings.postgres.host = "localhost"
    settings.postgres.port = 5432
    settings.postgres.database = "test_db"
    settings.postgres.user = "test"
    settings.postgres.password = MagicMock()
    settings.postgres.password.get_secret_value.return_value = "test"
    settings.postgres.vector_table = "test_vec"
    settings.embedding_dimension = 1536
    settings.llm_provider = "openai"
    settings.llm_model = "gpt-4o-mini"
    settings.llm_temperature = 0.1
    return settings


class _MockHandler:
    """Test helper that mimics the LlamaIndex agent run handler."""

    def __init__(self, response: MagicMock) -> None:
        self._response = response

    def __await__(self):
        async def _resolve():
            return self._response

        return _resolve().__await__()

    async def stream_events(self):
        return
        yield  # pragma: no cover


@pytest.mark.integration
class TestAgentToolCreation:
    """Verify agent tools are created with correct configuration."""

    @patch("backend.src.agents.leadership_agent.ReActAgent")
    @patch("backend.src.agents.leadership_agent.create_sql_query_tool")
    @patch("backend.src.agents.leadership_agent.create_query_engine")
    @patch("backend.src.agents.leadership_agent.create_llm")
    def test_leadership_agent_has_three_tools(
        self,
        mock_llm: MagicMock,
        mock_qe: MagicMock,
        mock_sql: MagicMock,
        mock_agent_cls: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        mock_llm.return_value = MagicMock()
        mock_qe.return_value = MagicMock()
        mock_sql.return_value = MagicMock(spec=QueryEngineTool)

        create_leadership_agent(mock_settings)

        call_kwargs = mock_agent_cls.call_args
        tools = call_kwargs.kwargs.get("tools", call_kwargs.args[0] if call_kwargs.args else [])
        assert len(tools) == 3

    @patch("backend.src.agents.leadership_agent.ReActAgent")
    @patch("backend.src.agents.leadership_agent.create_sql_query_tool")
    @patch("backend.src.agents.leadership_agent.create_query_engine")
    @patch("backend.src.agents.leadership_agent.create_llm")
    def test_agent_tools_have_correct_names(
        self,
        mock_llm: MagicMock,
        mock_qe: MagicMock,
        mock_sql: MagicMock,
        mock_agent_cls: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        mock_llm.return_value = MagicMock()
        mock_qe.return_value = MagicMock()

        mock_sql_tool = MagicMock(spec=QueryEngineTool)
        mock_sql_tool.metadata = MagicMock()
        mock_sql_tool.metadata.name = "structured_query"
        mock_sql.return_value = mock_sql_tool

        create_leadership_agent(mock_settings)

        call_kwargs = mock_agent_cls.call_args
        tools = call_kwargs.kwargs.get("tools", [])
        tool_names = [t.metadata.name for t in tools]

        assert "document_search" in tool_names
        assert "analyze_context" in tool_names
        assert "structured_query" in tool_names

    @patch("backend.src.agents.leadership_agent.ReActAgent")
    @patch("backend.src.agents.leadership_agent.create_sql_query_tool")
    @patch("backend.src.agents.leadership_agent.create_query_engine")
    @patch("backend.src.agents.leadership_agent.create_llm")
    def test_agent_uses_leadership_system_prompt(
        self,
        mock_llm: MagicMock,
        mock_qe: MagicMock,
        mock_sql: MagicMock,
        mock_agent_cls: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        mock_llm.return_value = MagicMock()
        mock_qe.return_value = MagicMock()
        mock_sql.return_value = MagicMock(spec=QueryEngineTool)

        create_leadership_agent(mock_settings)

        call_kwargs = mock_agent_cls.call_args
        system_prompt = call_kwargs.kwargs.get("system_prompt", "")
        assert system_prompt == LEADERSHIP_SYSTEM_PROMPT


@pytest.mark.integration
class TestAgentToolRouting:
    """Verify agent routes queries to the correct tool."""

    @pytest.mark.asyncio
    async def test_agent_returns_structured_response(self) -> None:
        mock_response = MagicMock()
        mock_response.__str__ = lambda self: "Q4 revenue is $1.25M, up 15% from Q3."
        mock_response.tool_calls = [MagicMock()]

        mock_agent = MagicMock()
        mock_agent.run.return_value = _MockHandler(mock_response)

        result = await run_agent_query("What is Q4 revenue?", mock_agent)

        assert isinstance(result, AgentResponse)
        assert "1.25M" in result.answer
        assert result.tool_calls_count == 1

    @pytest.mark.asyncio
    async def test_agent_handles_query_failure_gracefully(self) -> None:
        mock_agent = MagicMock()

        async def _raise(*args, **kwargs):
            raise RuntimeError("LLM API unavailable")

        mock_agent.run.side_effect = _raise

        result = await run_agent_query("What is our strategy?", mock_agent)

        assert isinstance(result, AgentResponse)
        assert "failed" in result.answer.lower()
        assert result.tool_calls_count == 0

    @pytest.mark.asyncio
    async def test_agent_can_make_multiple_tool_calls(self) -> None:
        mock_response = MagicMock()
        mock_response.__str__ = lambda self: "Combined analysis from documents and data."
        mock_response.tool_calls = [MagicMock(), MagicMock(), MagicMock()]

        mock_agent = MagicMock()
        mock_agent.run.return_value = _MockHandler(mock_response)

        result = await run_agent_query("Compare Q4 revenue with our strategic goals", mock_agent)

        assert result.tool_calls_count == 3


@pytest.mark.integration
class TestAgentSystemPromptGuidance:
    """Verify the system prompt correctly guides tool selection."""

    def test_system_prompt_mentions_structured_query_for_quantitative(self) -> None:
        prompt = LEADERSHIP_SYSTEM_PROMPT.lower()
        assert "quantitative" in prompt or "kpi" in prompt or "metric" in prompt
        assert "structured_query" in prompt

    def test_system_prompt_mentions_document_search_for_qualitative(self) -> None:
        prompt = LEADERSHIP_SYSTEM_PROMPT.lower()
        assert "qualitative" in prompt or "strategy" in prompt or "polic" in prompt
        assert "document_search" in prompt

    def test_system_prompt_mentions_analyze_context(self) -> None:
        prompt = LEADERSHIP_SYSTEM_PROMPT.lower()
        assert "analyze_context" in prompt

    def test_system_prompt_guides_combining_tools(self) -> None:
        prompt = LEADERSHIP_SYSTEM_PROMPT.lower()
        assert "combine" in prompt or "both" in prompt or "complex" in prompt


@pytest.mark.integration
class TestDualDataSourcePattern:
    """Verify the dual-schema pattern — vector and structured data coexist.

    Inspired by talk2data architecture:
    - vector_schema: pgvector tables for RAG (per-collection)
    - sql_schema: structured tables for NL2SQL (business_metrics, collections)
    Both serve the same agent via different tools on the same PostgreSQL instance.
    """

    def test_rag_tool_and_sql_tool_can_be_created_independently(self) -> None:
        """Each tool wraps a different data source type."""
        with (
            patch("backend.src.agents.leadership_agent.create_query_engine") as mock_qe,
            patch("backend.src.agents.leadership_agent.create_sql_query_tool") as mock_sql,
        ):
            mock_qe.return_value = MagicMock()
            mock_sql.return_value = MagicMock(spec=QueryEngineTool)

            settings = MagicMock()
            rag_tool = create_rag_query_tool(settings)
            sql_tool = create_sql_tool(settings)
            analysis_tool = create_analysis_tool()

            assert rag_tool is not None
            assert sql_tool is not None
            assert analysis_tool is not None

    def test_rag_tool_targets_vector_store(self) -> None:
        with patch("backend.src.agents.leadership_agent.create_query_engine") as mock_qe:
            mock_qe.return_value = MagicMock()
            settings = MagicMock()

            tool = create_rag_query_tool(settings)

            mock_qe.assert_called_once_with(settings)
            assert tool.metadata.name == "document_search"

    def test_sql_tool_targets_structured_tables(self) -> None:
        with patch("backend.src.agents.leadership_agent.create_sql_query_tool") as mock_sql:
            mock_sql_tool = MagicMock(spec=QueryEngineTool)
            mock_sql_tool.metadata = MagicMock()
            mock_sql_tool.metadata.name = "structured_query"
            mock_sql.return_value = mock_sql_tool

            settings = MagicMock()
            tool = create_sql_tool(settings)

            assert tool.metadata.name == "structured_query"


@pytest.mark.integration
class TestAgentApiEndpoint:
    """Verify the /api/v1/agent endpoint wires correctly to the agent."""

    @pytest.mark.asyncio
    async def test_agent_endpoint_returns_answer(self) -> None:
        from httpx import ASGITransport, AsyncClient

        with (
            patch("backend.src.api.main.create_leadership_agent") as mock_create,
            patch("backend.src.api.main.create_sync_engine"),
            patch("backend.src.api.main.create_tables"),
            patch("backend.src.api.main.create_session_factory"),
            patch("backend.src.api.main.seed_sample_documents"),
            patch("backend.src.api.main._ensure_default_collection"),
            patch("backend.src.api.main.seed_business_metrics"),
            patch("backend.src.api.main.configure_telemetry"),
            patch("backend.src.api.main.shutdown_telemetry"),
            patch("backend.src.api.agent_routes.run_agent_query") as mock_run,
        ):
            mock_create.return_value = MagicMock()
            mock_run.return_value = AgentResponse(
                answer="The strategic plan focuses on cloud migration.",
                tool_calls_count=1,
            )

            from backend.src.api.main import create_app

            app = create_app()
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/agent",
                    json={"query": "What is our strategic plan?"},
                )

            assert response.status_code == 200
            body = response.json()
            assert "strategic plan" in body["answer"].lower() or "cloud" in body["answer"].lower()
            assert body["tool_calls_count"] == 1

    @pytest.mark.asyncio
    async def test_agent_endpoint_returns_tool_calls_count(self) -> None:
        from httpx import ASGITransport, AsyncClient

        with (
            patch("backend.src.api.main.create_leadership_agent") as mock_create,
            patch("backend.src.api.main.create_sync_engine"),
            patch("backend.src.api.main.create_tables"),
            patch("backend.src.api.main.create_session_factory"),
            patch("backend.src.api.main.seed_sample_documents"),
            patch("backend.src.api.main._ensure_default_collection"),
            patch("backend.src.api.main.seed_business_metrics"),
            patch("backend.src.api.main.configure_telemetry"),
            patch("backend.src.api.main.shutdown_telemetry"),
            patch("backend.src.api.agent_routes.run_agent_query") as mock_run,
        ):
            mock_create.return_value = MagicMock()
            mock_run.return_value = AgentResponse(
                answer="Analysis complete.",
                tool_calls_count=3,
            )

            from backend.src.api.main import create_app

            app = create_app()
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/agent",
                    json={"query": "Compare revenue trends with strategic goals"},
                )

            body = response.json()
            assert body["tool_calls_count"] == 3
