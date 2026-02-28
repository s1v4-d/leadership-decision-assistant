"""Tests for the leadership agent module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.src.agents.leadership_agent import (
    analyze_leadership_context,
    create_analysis_tool,
    create_leadership_agent,
    create_rag_query_tool,
    run_agent_query,
    stream_agent_response,
)
from backend.src.agents.prompts import (
    ANALYSIS_TOOL_DESCRIPTION,
    LEADERSHIP_SYSTEM_PROMPT,
    RAG_TOOL_DESCRIPTION,
)
from backend.src.models.domain import AgentResponse


class _MockHandler:
    """Test helper that mimics the LlamaIndex agent run handler."""

    def __init__(self, response: MagicMock, events: list | None = None) -> None:
        self._response = response
        self._events = events or []

    def __await__(self):
        async def _resolve():
            return self._response

        return _resolve().__await__()

    async def stream_events(self):
        for event in self._events:
            yield event


class _FakeAgentStream:
    """Fake AgentStream event for testing stream_agent_response."""

    def __init__(self, delta: str) -> None:
        self.delta = delta


class TestPrompts:
    def test_leadership_system_prompt_is_non_empty(self) -> None:
        assert LEADERSHIP_SYSTEM_PROMPT
        assert "leadership" in LEADERSHIP_SYSTEM_PROMPT.lower()

    def test_rag_tool_description_is_non_empty(self) -> None:
        assert RAG_TOOL_DESCRIPTION
        assert "document" in RAG_TOOL_DESCRIPTION.lower()

    def test_analysis_tool_description_is_non_empty(self) -> None:
        assert ANALYSIS_TOOL_DESCRIPTION
        assert "analysis" in ANALYSIS_TOOL_DESCRIPTION.lower()


class TestAnalyzeLeadershipContext:
    def test_returns_formatted_analysis(self) -> None:
        result = analyze_leadership_context("Hiring plan", "Need 5 engineers")
        assert "Hiring plan" in result
        assert "Need 5 engineers" in result
        assert "Risks" in result
        assert "Opportunities" in result
        assert "Recommendations" in result

    def test_handles_empty_findings(self) -> None:
        result = analyze_leadership_context("Topic", "")
        assert "Topic" in result


class TestCreateRagQueryTool:
    @patch("backend.src.agents.leadership_agent.QueryEngineTool")
    @patch("backend.src.agents.leadership_agent.create_query_engine")
    def test_wraps_query_engine_as_tool(
        self,
        mock_create_engine: MagicMock,
        mock_tool_cls: MagicMock,
    ) -> None:
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_settings = MagicMock()

        create_rag_query_tool(mock_settings)

        mock_create_engine.assert_called_once_with(mock_settings)
        mock_tool_cls.from_defaults.assert_called_once_with(
            query_engine=mock_engine,
            name="document_search",
            description=RAG_TOOL_DESCRIPTION,
        )


class TestCreateAnalysisTool:
    @patch("backend.src.agents.leadership_agent.FunctionTool")
    def test_creates_function_tool(self, mock_tool_cls: MagicMock) -> None:
        create_analysis_tool()

        mock_tool_cls.from_defaults.assert_called_once_with(
            fn=analyze_leadership_context,
            name="analyze_context",
            description=ANALYSIS_TOOL_DESCRIPTION,
        )


class TestCreateLeadershipAgent:
    @patch("backend.src.agents.leadership_agent.ReActAgent")
    @patch("backend.src.agents.leadership_agent.create_analysis_tool")
    @patch("backend.src.agents.leadership_agent.create_rag_query_tool")
    @patch("backend.src.agents.leadership_agent.create_llm")
    def test_assembles_agent_with_correct_components(
        self,
        mock_create_llm: MagicMock,
        mock_create_rag: MagicMock,
        mock_create_analysis: MagicMock,
        mock_agent_cls: MagicMock,
    ) -> None:
        mock_llm = MagicMock()
        mock_create_llm.return_value = mock_llm
        mock_rag_tool = MagicMock()
        mock_create_rag.return_value = mock_rag_tool
        mock_analysis_tool = MagicMock()
        mock_create_analysis.return_value = mock_analysis_tool
        mock_settings = MagicMock()

        create_leadership_agent(mock_settings)

        mock_create_llm.assert_called_once_with(mock_settings)
        mock_create_rag.assert_called_once_with(mock_settings)
        mock_create_analysis.assert_called_once()
        mock_agent_cls.assert_called_once_with(
            tools=[mock_rag_tool, mock_analysis_tool],
            llm=mock_llm,
            system_prompt=LEADERSHIP_SYSTEM_PROMPT,
        )


class TestRunAgentQuery:
    @pytest.fixture()
    def mock_agent(self) -> MagicMock:
        mock_response = MagicMock()
        mock_response.__str__ = MagicMock(return_value="Strategic recommendation")
        mock_response.tool_calls = [MagicMock(), MagicMock()]
        agent = MagicMock()
        agent.run.return_value = _MockHandler(mock_response)
        return agent

    async def test_returns_agent_response(self, mock_agent: MagicMock) -> None:
        result = await run_agent_query("What should we do?", mock_agent)

        assert isinstance(result, AgentResponse)
        assert result.answer == "Strategic recommendation"
        assert result.tool_calls_count == 2

    async def test_passes_query_to_agent(self, mock_agent: MagicMock) -> None:
        await run_agent_query("budget question", mock_agent)

        call_kwargs = mock_agent.run.call_args
        assert call_kwargs[0][0] == "budget question"

    @patch("backend.src.agents.leadership_agent.Context")
    async def test_creates_context_when_none_provided(
        self,
        mock_context_cls: MagicMock,
        mock_agent: MagicMock,
    ) -> None:
        mock_ctx = MagicMock()
        mock_context_cls.return_value = mock_ctx

        await run_agent_query("question", mock_agent)

        mock_context_cls.assert_called_once_with(mock_agent)
        mock_agent.run.assert_called_once_with("question", ctx=mock_ctx)

    async def test_uses_provided_context(self, mock_agent: MagicMock) -> None:
        ctx = MagicMock()

        await run_agent_query("question", mock_agent, ctx=ctx)

        mock_agent.run.assert_called_once_with("question", ctx=ctx)

    async def test_returns_error_response_on_failure(self) -> None:
        agent = MagicMock()
        agent.run.side_effect = RuntimeError("LLM timeout")

        result = await run_agent_query("question", agent)

        assert "Agent query failed" in result.answer
        assert "LLM timeout" in result.answer
        assert result.tool_calls_count == 0

    async def test_handles_none_tool_calls(self) -> None:
        mock_response = MagicMock()
        mock_response.__str__ = MagicMock(return_value="answer")
        mock_response.tool_calls = None
        agent = MagicMock()
        agent.run.return_value = _MockHandler(mock_response)

        result = await run_agent_query("question", agent)

        assert result.tool_calls_count == 0


class TestStreamAgentResponse:
    async def test_yields_stream_deltas(self) -> None:
        event_1 = _FakeAgentStream("Hello ")
        event_2 = _FakeAgentStream("World")
        mock_response = MagicMock()

        agent = MagicMock()
        agent.run.return_value = _MockHandler(mock_response, events=[event_1, event_2])
        ctx = MagicMock()

        with patch(
            "backend.src.agents.leadership_agent.AgentStream",
            _FakeAgentStream,
        ):
            chunks = [chunk async for chunk in stream_agent_response("query", agent, ctx=ctx)]

        assert chunks == ["Hello ", "World"]

    async def test_yields_error_on_failure(self) -> None:
        agent = MagicMock()
        agent.run.side_effect = RuntimeError("stream error")
        ctx = MagicMock()

        chunks = [chunk async for chunk in stream_agent_response("query", agent, ctx=ctx)]

        assert len(chunks) == 1
        assert "Agent stream failed" in chunks[0]

    @patch("backend.src.agents.leadership_agent.Context")
    async def test_creates_context_when_none_provided(
        self,
        mock_context_cls: MagicMock,
    ) -> None:
        mock_response = MagicMock()
        agent = MagicMock()
        agent.run.return_value = _MockHandler(mock_response, events=[])
        mock_ctx = MagicMock()
        mock_context_cls.return_value = mock_ctx

        _ = [chunk async for chunk in stream_agent_response("query", agent)]

        mock_context_cls.assert_called_once_with(agent)
