from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


TOKEN_PATTERN = re.compile(r"\S+")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
PAGE_HEADING_PATTERN = re.compile(r"^Page\s+(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class ChunkingParams:
    strategy: str = "heading_recursive"
    chunk_size: int = 900
    chunk_overlap: int = 120
    tokenizer: str = "cl100k_base"
    preserve_headings: bool = True
    preserve_tables: bool = True
    page_boundary_mode: str = "soft"


@dataclass(frozen=True)
class PreparedFile:
    original_name: str
    path: Path
    stored_path: str


def preview_prepared_asset_chunks(
    *,
    storage_path: str,
    manifest_json: dict[str, Any],
    chunking: ChunkingParams,
    max_chunks: int = 50,
    text_preview_chars: int = 900,
) -> dict[str, Any]:
    warnings = _validate_params(chunking)
    files = _prepared_files(storage_path, manifest_json)
    chunks: list[dict[str, Any]] = []
    chunks_by_file: dict[str, int] = {}

    for prepared_file in files:
        text = prepared_file.path.read_text(encoding="utf-8", errors="replace")
        file_chunks = chunk_text(
            text,
            chunking=chunking,
            source_name=prepared_file.original_name,
            stored_path=prepared_file.stored_path,
        )
        chunks_by_file[prepared_file.original_name] = len(file_chunks)
        chunks.extend(file_chunks)

    if not files:
        warnings.append("No supported prepared text or Markdown files were found.")
    if not chunks:
        warnings.append("Chunking produced no chunks.")

    for index, chunk in enumerate(chunks, start=1):
        chunk["chunk_id"] = f"preview_{index:06d}"
        chunk_text_value = str(chunk.pop("text"))
        chunk["text_preview"] = _clip(chunk_text_value, text_preview_chars)

    visible_chunks = chunks[:max_chunks]
    if len(chunks) > max_chunks:
        warnings.append(f"Preview truncated to {max_chunks} of {len(chunks)} chunks.")

    token_counts = [int(chunk["token_count"]) for chunk in chunks]
    char_counts = [int(chunk["char_count"]) for chunk in chunks]
    summary = {
        "chunk_count": len(chunks),
        "files_count": len(files),
        "min_tokens": min(token_counts) if token_counts else 0,
        "avg_tokens": round(mean(token_counts), 1) if token_counts else 0,
        "max_tokens": max(token_counts) if token_counts else 0,
        "min_chars": min(char_counts) if char_counts else 0,
        "avg_chars": round(mean(char_counts), 1) if char_counts else 0,
        "max_chars": max(char_counts) if char_counts else 0,
        "chunks_by_file": [
            {"source_name": source_name, "chunk_count": chunk_count}
            for source_name, chunk_count in chunks_by_file.items()
        ],
        "token_counter": f"{chunking.tokenizer}:approx_whitespace",
    }
    return {"chunks": visible_chunks, "summary": summary, "warnings": warnings}


def chunk_text(
    text: str,
    *,
    chunking: ChunkingParams,
    source_name: str,
    stored_path: str,
) -> list[dict[str, Any]]:
    if chunking.strategy == "heading_recursive":
        sections = _markdown_sections(text, preserve_headings=chunking.preserve_headings)
    else:
        sections = [
            {
                "heading_path": [],
                "page": None,
                "section": None,
                "text": text,
            }
        ]

    chunks: list[dict[str, Any]] = []
    for section in sections:
        section_text = str(section["text"]).strip()
        if not section_text:
            continue
        for chunk_text_value in _chunk_by_tokens(
            section_text,
            chunk_size=chunking.chunk_size,
            chunk_overlap=chunking.chunk_overlap,
        ):
            chunks.append(
                {
                    "char_count": len(chunk_text_value),
                    "heading_path": section["heading_path"],
                    "page": section["page"],
                    "section": section["section"],
                    "source_name": source_name,
                    "stored_path": stored_path,
                    "text": chunk_text_value,
                    "token_count": _count_tokens(chunk_text_value),
                }
            )
    return chunks


def _validate_params(chunking: ChunkingParams) -> list[str]:
    warnings: list[str] = []
    if chunking.strategy not in {"recursive", "heading_recursive"}:
        raise ValueError("Unsupported chunking strategy")
    if chunking.chunk_size < 100:
        warnings.append("Chunk size is very small; retrieval may lose context.")
    if chunking.chunk_overlap >= chunking.chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    if chunking.chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")
    if chunking.page_boundary_mode not in {"soft", "ignore"}:
        raise ValueError("Unsupported page_boundary_mode")
    if chunking.strategy == "recursive" and chunking.preserve_headings:
        warnings.append("preserve_headings only affects heading_recursive strategy.")
    return warnings


def _prepared_files(storage_path: str, manifest_json: dict[str, Any]) -> list[PreparedFile]:
    base_dir = Path(storage_path)
    prepared_files: list[PreparedFile] = []
    for file_entry in manifest_json.get("files", []):
        stored_path = file_entry.get("stored_path")
        original_name = str(file_entry.get("original_name") or "")
        if not isinstance(stored_path, str):
            continue
        suffix = Path(original_name).suffix.lower()
        content_type = str(file_entry.get("content_type") or "")
        if suffix not in {".md", ".markdown", ".txt"} and content_type not in {
            "text/markdown",
            "text/plain",
        }:
            continue
        path = base_dir / stored_path
        if path.exists():
            prepared_files.append(
                PreparedFile(
                    original_name=original_name or path.name,
                    path=path,
                    stored_path=stored_path,
                )
            )
    return prepared_files


def _markdown_sections(text: str, *, preserve_headings: bool) -> list[dict[str, Any]]:
    lines = text.splitlines()
    sections: list[dict[str, Any]] = []
    current_lines: list[str] = []
    current_heading_path: list[str] = []
    current_section: str | None = None
    current_page: int | None = None
    heading_stack: list[tuple[int, str]] = []

    def flush() -> None:
        section_text = "\n".join(current_lines).strip()
        if section_text:
            sections.append(
                {
                    "heading_path": list(current_heading_path),
                    "page": current_page,
                    "section": current_section,
                    "text": section_text,
                }
            )

    for line in lines:
        match = HEADING_PATTERN.match(line)
        if match:
            flush()
            current_lines = [line] if preserve_headings else []
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack = [(item_level, item_title) for item_level, item_title in heading_stack if item_level < level]
            heading_stack.append((level, title))
            current_heading_path = [item_title for _, item_title in heading_stack]
            current_section = title
            page_match = PAGE_HEADING_PATTERN.match(title)
            current_page = int(page_match.group(1)) if page_match else current_page
            continue
        current_lines.append(line)

    flush()
    if sections:
        return sections
    return [{"heading_path": [], "page": None, "section": None, "text": text}]


def _chunk_by_tokens(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    tokens = list(TOKEN_PATTERN.finditer(text))
    if not tokens:
        return []
    if len(tokens) <= chunk_size:
        return [text.strip()]

    chunks: list[str] = []
    step = max(1, chunk_size - chunk_overlap)
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        char_start = tokens[start].start()
        char_end = tokens[end - 1].end()
        chunk = text[char_start:char_end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(tokens):
            break
        start += step
    return chunks


def _count_tokens(text: str) -> int:
    return len(TOKEN_PATTERN.findall(text))


def _clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
