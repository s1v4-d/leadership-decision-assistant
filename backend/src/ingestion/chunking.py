"""Semantic document chunking strategies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from llama_index.core.node_parser import SentenceSplitter

if TYPE_CHECKING:
    from backend.src.core.config import RAGSettings


def create_sentence_splitter(rag_settings: RAGSettings) -> SentenceSplitter:
    """Create a SentenceSplitter configured from RAG settings."""
    return SentenceSplitter(
        chunk_size=rag_settings.chunk_size,
        chunk_overlap=rag_settings.chunk_overlap,
    )
