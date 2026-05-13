from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


TOKEN_PATTERN = re.compile(r"\S+")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
PAGE_HEADING_PATTERN = re.compile(r"^Page\s+(\d+)$", re.IGNORECASE)

Chunk = dict[str, Any]
Section = dict[str, Any]
StrategyChunker = Callable[[str, "ChunkingParams", str, str], list[Chunk]]


@dataclass(frozen=True)
class ChunkingParamField:
    name: str
    label: str
    field_type: str
    default: Any
    help_text: str | None = None
    min_value: int | None = None
    max_value: int | None = None
    options: list[dict[str, str]] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "default": self.default,
            "label": self.label,
            "name": self.name,
            "type": self.field_type,
        }
        if self.help_text:
            payload["help_text"] = self.help_text
        if self.min_value is not None:
            payload["min"] = self.min_value
        if self.max_value is not None:
            payload["max"] = self.max_value
        if self.options is not None:
            payload["options"] = self.options
        return payload


@dataclass(frozen=True)
class ChunkingStrategy:
    id: str
    label: str
    description: str
    fields: list[ChunkingParamField]
    chunker: StrategyChunker
    adapter: str = "native"
    implementation: str | None = None
    library: str | None = None

    @property
    def defaults(self) -> dict[str, Any]:
        return {field.name: field.default for field in self.fields}

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter,
            "default_params": self.defaults,
            "description": self.description,
            "fields": [field.to_dict() for field in self.fields],
            "id": self.id,
            "implementation": self.implementation,
            "label": self.label,
            "library": self.library,
        }


@dataclass(frozen=True)
class ChunkingParams:
    strategy: str = "heading_recursive"
    params: dict[str, Any] | None = None

    def merged_params(self) -> dict[str, Any]:
        strategy = get_chunking_strategy(self.strategy)
        params = strategy.defaults
        params.update(self.params or {})
        return _coerce_params(strategy, params)


@dataclass(frozen=True)
class PreparedFile:
    original_name: str
    path: Path
    stored_path: str


COMMON_FIELDS = [
    ChunkingParamField(
        name="chunk_size",
        label="Chunk size",
        field_type="number",
        default=900,
        help_text="Approximate whitespace-token target per chunk.",
        min_value=1,
        max_value=8000,
    ),
    ChunkingParamField(
        name="chunk_overlap",
        label="Overlap",
        field_type="number",
        default=120,
        help_text="Approximate whitespace-token overlap between adjacent chunks.",
        min_value=0,
        max_value=4000,
    ),
    ChunkingParamField(
        name="tokenizer",
        label="Tokenizer",
        field_type="select",
        default="cl100k_base",
        options=[
            {"label": "cl100k_base", "value": "cl100k_base"},
            {"label": "Approximate words", "value": "approx_words"},
        ],
    ),
    ChunkingParamField(
        name="page_boundary_mode",
        label="Page boundaries",
        field_type="select",
        default="soft",
        options=[
            {"label": "Soft", "value": "soft"},
            {"label": "Ignore", "value": "ignore"},
        ],
    ),
]

LANGCHAIN_RECURSIVE_CHARACTER_FIELDS = [
    ChunkingParamField(
        name="chunk_size",
        label="Chunk size",
        field_type="number",
        default=1000,
        help_text="Maximum chunk length passed to RecursiveCharacterTextSplitter.",
        min_value=1,
        max_value=20000,
    ),
    ChunkingParamField(
        name="chunk_overlap",
        label="Overlap",
        field_type="number",
        default=200,
        help_text="Overlap length passed to RecursiveCharacterTextSplitter.",
        min_value=0,
        max_value=10000,
    ),
    ChunkingParamField(
        name="separators",
        label="Separators",
        field_type="text",
        default="\\n\\n|\\n| |",
        help_text="Pipe-separated separators. Leave the trailing item empty to include an empty-string fallback.",
    ),
    ChunkingParamField(
        name="keep_separator",
        label="Keep separator",
        field_type="boolean",
        default=True,
    ),
    ChunkingParamField(
        name="is_separator_regex",
        label="Regex separators",
        field_type="boolean",
        default=False,
    ),
]

CHUNKING_STRATEGIES: dict[str, ChunkingStrategy] = {
    "heading_recursive": ChunkingStrategy(
        id="heading_recursive",
        label="Heading recursive",
        description="Split Markdown by headings first, then recursively split long sections.",
        fields=[
            *COMMON_FIELDS,
            ChunkingParamField(
                name="preserve_headings",
                label="Preserve headings",
                field_type="boolean",
                default=True,
                help_text="Include Markdown headings in section text before splitting.",
            ),
            ChunkingParamField(
                name="preserve_tables",
                label="Preserve tables",
                field_type="boolean",
                default=True,
                help_text="Reserved for table-aware splitting; currently kept in snapshots.",
            ),
        ],
        chunker=lambda text, chunking, source_name, stored_path: _chunk_sections(
            _markdown_sections(
                text,
                preserve_headings=bool(chunking.merged_params()["preserve_headings"]),
            ),
            chunking=chunking,
            source_name=source_name,
            stored_path=stored_path,
        ),
    ),
    "recursive": ChunkingStrategy(
        id="recursive",
        label="Recursive",
        description="Split each prepared text file directly by approximate token windows.",
        fields=COMMON_FIELDS,
        chunker=lambda text, chunking, source_name, stored_path: _chunk_sections(
            [{"heading_path": [], "page": None, "section": None, "text": text}],
            chunking=chunking,
            source_name=source_name,
            stored_path=stored_path,
        ),
    ),
    "langchain_recursive_character": ChunkingStrategy(
        id="langchain_recursive_character",
        label="LangChain RecursiveCharacter",
        description="Use LangChain RecursiveCharacterTextSplitter as an adapter-backed chunking strategy.",
        fields=LANGCHAIN_RECURSIVE_CHARACTER_FIELDS,
        chunker=lambda text, chunking, source_name, stored_path: _chunk_langchain_recursive_character(
            text,
            chunking=chunking,
            source_name=source_name,
            stored_path=stored_path,
        ),
        adapter="langchain",
        implementation="RecursiveCharacterTextSplitter",
        library="langchain-text-splitters",
    ),
}


def list_chunking_strategies() -> list[dict[str, Any]]:
    return [strategy.to_dict() for strategy in CHUNKING_STRATEGIES.values()]


def get_chunking_strategy(strategy_id: str) -> ChunkingStrategy:
    strategy = CHUNKING_STRATEGIES.get(strategy_id)
    if strategy is None:
        raise ValueError(f"Unsupported chunking strategy: {strategy_id}")
    return strategy


def preview_prepared_asset_chunks(
    *,
    storage_path: str,
    manifest_json: dict[str, Any],
    chunking: ChunkingParams,
    max_chunks: int = 50,
    text_preview_chars: int = 900,
) -> dict[str, Any]:
    strategy = get_chunking_strategy(chunking.strategy)
    params = chunking.merged_params()
    warnings = _validate_common_params(strategy, params)
    normalized_chunking = ChunkingParams(strategy=chunking.strategy, params=params)
    files = _prepared_files(storage_path, manifest_json)
    chunks: list[Chunk] = []
    chunks_by_file: dict[str, int] = {}

    for prepared_file in files:
        text = prepared_file.path.read_text(encoding="utf-8", errors="replace")
        file_chunks = strategy.chunker(
            text,
            normalized_chunking,
            prepared_file.original_name,
            prepared_file.stored_path,
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
        "strategy": strategy.id,
        "token_counter": f"{params.get('tokenizer', 'characters')}:approx_whitespace",
    }
    return {"chunks": visible_chunks, "summary": summary, "warnings": warnings}


def chunk_text(
    text: str,
    *,
    chunking: ChunkingParams,
    source_name: str,
    stored_path: str,
) -> list[Chunk]:
    strategy = get_chunking_strategy(chunking.strategy)
    normalized_chunking = ChunkingParams(strategy=chunking.strategy, params=chunking.merged_params())
    return strategy.chunker(text, normalized_chunking, source_name, stored_path)


def _coerce_params(strategy: ChunkingStrategy, params: dict[str, Any]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    fields_by_name = {field.name: field for field in strategy.fields}
    for name, field in fields_by_name.items():
        value = params.get(name, field.default)
        if field.field_type == "number":
            try:
                value = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be a number") from exc
        elif field.field_type == "boolean":
            value = bool(value)
        elif field.field_type == "select":
            value = str(value)
            options = field.options or []
            allowed = {option["value"] for option in options}
            if value not in allowed:
                raise ValueError(f"Unsupported value for {name}")
        else:
            value = str(value)
        coerced[name] = value
    return coerced


def _validate_common_params(strategy: ChunkingStrategy, params: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    chunk_size = int(params["chunk_size"])
    chunk_overlap = int(params["chunk_overlap"])
    if chunk_size < 100:
        warnings.append("Chunk size is very small; retrieval may lose context.")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")
    if strategy.id == "recursive" and "preserve_headings" in params:
        warnings.append("preserve_headings only affects heading_recursive strategy.")
    return warnings


def _chunk_langchain_recursive_character(
    text: str,
    *,
    chunking: ChunkingParams,
    source_name: str,
    stored_path: str,
) -> list[Chunk]:
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise ValueError(
            "langchain-text-splitters is required for langchain_recursive_character"
        ) from exc

    params = chunking.merged_params()
    splitter = RecursiveCharacterTextSplitter(
        chunk_overlap=int(params["chunk_overlap"]),
        chunk_size=int(params["chunk_size"]),
        is_separator_regex=bool(params["is_separator_regex"]),
        keep_separator=bool(params["keep_separator"]),
        length_function=len,
        separators=_parse_langchain_separators(str(params["separators"])),
    )
    chunks: list[Chunk] = []
    for chunk_text_value in splitter.split_text(text):
        if not chunk_text_value.strip():
            continue
        chunks.append(
            {
                "char_count": len(chunk_text_value),
                "heading_path": [],
                "page": None,
                "section": None,
                "source_name": source_name,
                "stored_path": stored_path,
                "text": chunk_text_value.strip(),
                "token_count": _count_tokens(chunk_text_value),
            }
        )
    return chunks


def _parse_langchain_separators(raw_value: str) -> list[str]:
    separators = raw_value.split("|")
    if not separators:
        return ["\n\n", "\n", " ", ""]
    return [separator.encode("utf-8").decode("unicode_escape") for separator in separators]


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


def _chunk_sections(
    sections: list[Section],
    *,
    chunking: ChunkingParams,
    source_name: str,
    stored_path: str,
) -> list[Chunk]:
    params = chunking.merged_params()
    chunks: list[Chunk] = []
    for section in sections:
        section_text = str(section["text"]).strip()
        if not section_text:
            continue
        for chunk_text_value in _chunk_by_tokens(
            section_text,
            chunk_size=int(params["chunk_size"]),
            chunk_overlap=int(params["chunk_overlap"]),
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


def _markdown_sections(text: str, *, preserve_headings: bool) -> list[Section]:
    lines = text.splitlines()
    sections: list[Section] = []
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
            heading_stack = [
                (item_level, item_title)
                for item_level, item_title in heading_stack
                if item_level < level
            ]
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
