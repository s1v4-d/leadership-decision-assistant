"""Agent API routes — POST /api/v1/agent with optional SSE streaming."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import structlog
from fastapi import APIRouter, Depends
from llama_index.core.agent.workflow import ReActAgent
from sse_starlette import EventSourceResponse, ServerSentEvent

from backend.src.agents.leadership_agent import (
    run_agent_query,
    stream_agent_response,
)
from backend.src.api.dependencies import SettingsDep  # noqa: TC001
from backend.src.core.security import (
    PromptInjectionError,
    detect_prompt_injection,
    parse_blocked_patterns,
    sanitize_query,
)
from backend.src.models.schemas import AgentQueryResponse, AgentRequest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)

agent_router = APIRouter(prefix="/api/v1", tags=["agent"])

_agent_instance: ReActAgent | None = None


def set_agent(agent: ReActAgent) -> None:
    """Store the agent singleton created during lifespan."""
    global _agent_instance  # noqa: PLW0603
    _agent_instance = agent


def get_leadership_agent() -> ReActAgent:
    """FastAPI dependency that returns the shared agent instance."""
    if _agent_instance is None:
        msg = "Agent not initialized. Check application startup."
        raise RuntimeError(msg)
    return _agent_instance


AgentDep = Annotated[ReActAgent, Depends(get_leadership_agent)]


def _sanitize(query: str, settings: SettingsDep) -> str:
    sanitized = sanitize_query(query, max_length=settings.security.max_query_length)
    blocked = parse_blocked_patterns(settings.security.blocked_patterns)
    if detect_prompt_injection(sanitized, blocked):
        raise PromptInjectionError("Prompt injection detected in query")
    return sanitized


async def _stream_events(query: str, agent: ReActAgent) -> AsyncGenerator[ServerSentEvent]:
    async for delta in stream_agent_response(query, agent):
        yield ServerSentEvent(data=delta, event="answer")
    yield ServerSentEvent(data="", event="done")


@agent_router.post("/agent", response_model=AgentQueryResponse)
async def query_agent(
    body: AgentRequest,
    settings: SettingsDep,
    agent: AgentDep,
) -> AgentQueryResponse | EventSourceResponse:
    """Run the leadership agent and return the response."""
    logger.info("agent_query_received", query_length=len(body.query), stream=body.stream)
    sanitized = _sanitize(body.query, settings)

    if body.stream:
        return EventSourceResponse(_stream_events(sanitized, agent))

    result = await run_agent_query(sanitized, agent)
    logger.info("agent_query_complete", tool_calls=result.tool_calls_count)
    return AgentQueryResponse(answer=result.answer, tool_calls_count=result.tool_calls_count)
