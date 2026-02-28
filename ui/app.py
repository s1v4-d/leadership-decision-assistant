"""Streamlit application for the Leadership Decision Assistant."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import streamlit as st

from ui.api_client import (
    check_health,
    ingest_documents,
    query_documents,
    query_documents_stream,
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

_HTTP_RATE_LIMITED = 429
_HTTP_UNPROCESSABLE = 422


def _render_sources(sources: list[dict[str, Any]]) -> None:
    """Display source documents in an expandable section."""
    with st.expander(f"📚 Sources ({len(sources)})", expanded=False):
        for i, source in enumerate(sources, 1):
            score = source.get("score", 0.0)
            st.markdown(f"**Source {i}** (relevance: {score:.2f})")
            st.text(source.get("text", "")[:500])
            if source.get("metadata"):
                st.caption(f"Metadata: {source['metadata']}")
            if i < len(sources):
                st.divider()


def _handle_http_error(exc: httpx.HTTPStatusError) -> None:
    """Display HTTP error messages to the user."""
    status = exc.response.status_code
    if status == _HTTP_RATE_LIMITED:
        error_msg = "⚠️ Rate limit exceeded. Please wait a moment."
    elif status == _HTTP_UNPROCESSABLE:
        error_msg = "⚠️ Invalid query. Please check your input."
    else:
        error_msg = f"⚠️ Server error ({status}). Please try again."
    st.error(error_msg)
    st.session_state.messages.append({"role": "assistant", "content": error_msg})


def _handle_streaming_query(prompt: str) -> None:
    """Handle a streaming query with real-time display."""
    answer_text = ""
    sources: list[dict[str, Any]] = []

    try:
        placeholder = st.empty()
        with st.spinner("Searching documents..."):
            for event_type, data in query_documents_stream(BACKEND_URL, prompt):
                if event_type == "answer":
                    answer_text = data
                    placeholder.markdown(answer_text)
                elif event_type == "sources":
                    sources = json.loads(data) if data else []
                elif event_type == "done":
                    break

        if not answer_text:
            answer_text = "No answer received from the agent."
            placeholder.markdown(answer_text)

        if sources:
            _render_sources(sources)

        st.session_state.messages.append({"role": "assistant", "content": answer_text, "sources": sources})
    except httpx.HTTPStatusError as exc:
        _handle_http_error(exc)
    except httpx.HTTPError as exc:
        error_msg = f"⚠️ Connection error: {exc}"
        st.error(error_msg)
        st.session_state.messages.append({"role": "assistant", "content": error_msg})


def _handle_standard_query(prompt: str) -> None:
    """Handle a non-streaming query."""
    try:
        with st.spinner("Searching documents..."):
            result = query_documents(BACKEND_URL, prompt)

        answer_text = result.get("answer", "No answer received.")
        sources = result.get("sources", [])
        cached = result.get("cached", False)

        st.markdown(answer_text)
        if cached:
            st.caption("📋 Cached response")
        if sources:
            _render_sources(sources)

        st.session_state.messages.append({"role": "assistant", "content": answer_text, "sources": sources})
    except httpx.HTTPStatusError as exc:
        _handle_http_error(exc)
    except httpx.HTTPError as exc:
        error_msg = f"⚠️ Connection error: {exc}"
        st.error(error_msg)
        st.session_state.messages.append({"role": "assistant", "content": error_msg})


def _render_sidebar() -> tuple[bool, bool]:
    """Render the sidebar and return (healthy, stream_enabled)."""
    with st.sidebar:
        st.title("📊 Leadership Agent")
        st.markdown("**AI-powered insights from your company documents**")

        healthy = check_health(BACKEND_URL)
        if healthy:
            st.success("Backend: Connected", icon="✅")
        else:
            st.error("Backend: Unavailable", icon="❌")

        st.markdown("---")
        st.markdown("### Document Upload")
        uploaded_files = st.file_uploader(
            "Upload company documents",
            accept_multiple_files=True,
            type=["pdf", "docx", "xlsx", "txt", "md", "csv"],
        )

        if uploaded_files:
            st.info(f"📁 {len(uploaded_files)} file(s) selected")
            if st.button("📤 Ingest Documents", type="primary"):
                with st.spinner("Uploading and processing..."):
                    try:
                        result = ingest_documents(BACKEND_URL, uploaded_files)
                        st.success(f"✅ {result['message']}")
                    except httpx.HTTPStatusError as exc:
                        st.error(f"Ingestion failed: {exc.response.status_code}")
                    except httpx.HTTPError as exc:
                        st.error(f"Connection error: {exc}")

        st.markdown("---")
        st.markdown("### Settings")
        stream_enabled = st.checkbox("Stream responses", value=True)

        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()

    return healthy, stream_enabled


def main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(
        page_title="AI Leadership Insight Agent",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    healthy, stream_enabled = _render_sidebar()

    st.title("🤖 AI Leadership Insight Agent")
    st.caption("Ask questions about your company's performance, strategy, and operations")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                _render_sources(message["sources"])

    if prompt := st.chat_input("Ask a leadership question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if not healthy:
                answer = "⚠️ Backend is unavailable. Please check the connection."
                st.warning(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            elif stream_enabled:
                _handle_streaming_query(prompt)
            else:
                _handle_standard_query(prompt)


main()
