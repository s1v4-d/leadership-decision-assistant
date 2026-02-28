"""LlamaIndex ReAct agent for leadership decision support."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from llama_index.core.agent.workflow import AgentStream, ReActAgent
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.core.workflow import Context

from backend.src.agents.prompts import (
    ANALYSIS_TOOL_DESCRIPTION,
    LEADERSHIP_SYSTEM_PROMPT,
    RAG_TOOL_DESCRIPTION,
)
from backend.src.core.llm_provider import create_llm
from backend.src.models.domain import AgentResponse
from backend.src.tools.rag_tool import create_query_engine
from backend.src.tools.sql_tool import create_sql_query_tool

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from backend.src.core.config import Settings

logger = structlog.get_logger(__name__)


def analyze_leadership_context(topic: str, key_findings: str) -> str:
    """Organize leadership analysis into risks, opportunities, and recommendations."""
    return (
        f"## Leadership Analysis: {topic}\n\n"
        f"### Key Findings\n{key_findings}\n\n"
        "Please structure this into:\n"
        "1. **Risks** — potential threats or downsides\n"
        "2. **Opportunities** — potential benefits or upsides\n"
        "3. **Recommendations** — suggested actions with rationale"
    )


def create_rag_query_tool(settings: Settings) -> QueryEngineTool:
    """Wrap the RAG query engine as a tool for agent use."""
    query_engine = create_query_engine(settings)
    return QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name="document_search",
        description=RAG_TOOL_DESCRIPTION,
    )


def create_analysis_tool() -> FunctionTool:
    """Create a FunctionTool for structured leadership analysis."""
    return FunctionTool.from_defaults(
        fn=analyze_leadership_context,
        name="analyze_context",
        description=ANALYSIS_TOOL_DESCRIPTION,
    )


def create_sql_tool(settings: Settings) -> QueryEngineTool:
    """Create a QueryEngineTool wrapping the NL2SQL engine."""
    return create_sql_query_tool(settings)


def create_leadership_agent(settings: Settings) -> ReActAgent:
    """Build a ReActAgent with RAG, analysis, and SQL tools."""
    llm = create_llm(settings)
    rag_tool = create_rag_query_tool(settings)
    analysis_tool = create_analysis_tool()
    sql_tool = create_sql_tool(settings)

    return ReActAgent(
        tools=[rag_tool, analysis_tool, sql_tool],
        llm=llm,
        system_prompt=LEADERSHIP_SYSTEM_PROMPT,
    )


async def run_agent_query(
    query: str,
    agent: ReActAgent,
    ctx: Context | None = None,
    *,
    collection_id: str | None = None,
) -> AgentResponse:
    """Run the agent and return a structured response.

    When *collection_id* is provided it is prepended to the user message
    as a metadata hint so that tool implementations can scope their
    retrieval accordingly.
    """
    if ctx is None:
        ctx = Context(agent)

    user_msg = query
    if collection_id:
        user_msg = f"[collection_id={collection_id}] {query}"

    try:
        handler = agent.run(user_msg, ctx=ctx)
        response = await handler
        answer = str(response)
        tool_calls_count = len(response.tool_calls) if response.tool_calls else 0

        logger.info(
            "agent_query_completed",
            query_length=len(query),
            tool_calls=tool_calls_count,
            collection_id=collection_id,
        )

        return AgentResponse(answer=answer, tool_calls_count=tool_calls_count)
    except Exception as exc:
        logger.exception("agent_query_failed", error=str(exc))
        return AgentResponse(answer=f"Agent query failed: {exc}", tool_calls_count=0)


async def stream_agent_response(
    query: str,
    agent: ReActAgent,
    ctx: Context | None = None,
) -> AsyncGenerator[str, None]:
    """Stream agent response deltas for SSE."""
    if ctx is None:
        ctx = Context(agent)

    try:
        handler = agent.run(query, ctx=ctx)
        async for event in handler.stream_events():
            if isinstance(event, AgentStream):
                yield event.delta
        await handler
    except Exception as exc:
        logger.exception("agent_stream_failed", error=str(exc))
        yield f"Agent stream failed: {exc}"
