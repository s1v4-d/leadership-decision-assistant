"""File format parsers for PDF, DOCX, and XLSX documents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from llama_index.core import SimpleDirectoryReader

if TYPE_CHECKING:
    from pathlib import Path

    from llama_index.core.schema import Document

SUPPORTED_EXTENSIONS: list[str] = [
    ".pdf",
    ".docx",
    ".txt",
    ".xlsx",
    ".csv",
    ".md",
]


def load_documents(directory: Path) -> list[Document]:
    """Load documents from a directory using LlamaIndex SimpleDirectoryReader."""
    if not directory.exists():
        msg = f"Directory does not exist: {directory}"
        raise FileNotFoundError(msg)

    reader = SimpleDirectoryReader(
        input_dir=directory,
        required_exts=SUPPORTED_EXTENSIONS,
        recursive=True,
    )
    return reader.load_data()  # type: ignore[no-any-return]
