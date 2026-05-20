from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.hashing import stable_json_dumps


TOKEN_PATTERN_CHARS = "\n\t "


def build_docling_parent_unit_files(
    *,
    docling_document: dict[str, Any],
    max_chapter_tokens: int,
    source_name: str,
    stem: str,
) -> list[dict[str, Any]]:
    elements = _ordered_docling_elements(docling_document)
    if not elements:
        return []

    pages = _build_page_units(elements=elements, source_name=source_name)
    chapters = _build_chapter_units(
        elements=elements,
        max_chapter_tokens=max_chapter_tokens,
        pages=pages,
        source_name=source_name,
    )
    generated: list[dict[str, Any]] = []
    if pages:
        generated.append(
            {
                "content": _jsonl_bytes(pages),
                "content_type": "application/x-jsonlines",
                "original_name": f"{stem}.pages.jsonl",
                "role": "prepared_parent_pages",
                "source": {"original_name": source_name},
            }
        )
    if chapters:
        generated.append(
            {
                "content": _jsonl_bytes(chapters),
                "content_type": "application/x-jsonlines",
                "original_name": f"{stem}.chapters.jsonl",
                "role": "prepared_parent_chapters",
                "source": {"original_name": source_name},
            }
        )
    return generated


def read_parent_units_from_prepared_asset(
    *,
    manifest_json: dict[str, Any],
    parent_type: str,
    storage_path: str,
) -> dict[str, dict[str, Any]]:
    role = "prepared_parent_pages" if parent_type == "page" else "prepared_parent_chapters"
    base_dir = Path(storage_path)
    units: dict[str, dict[str, Any]] = {}
    for file_entry in manifest_json.get("files", []):
        if str(file_entry.get("role") or "") != role:
            continue
        stored_path = file_entry.get("stored_path")
        if not isinstance(stored_path, str):
            continue
        path = base_dir / stored_path
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            parent_id = str(item.get("parent_id") or "")
            if parent_id:
                units[parent_id] = item
    return units


def _ordered_docling_elements(docling_document: dict[str, Any]) -> list[dict[str, Any]]:
    texts = docling_document.get("texts")
    tables = docling_document.get("tables")
    by_ref: dict[str, dict[str, Any]] = {}
    if isinstance(texts, list):
        for item in texts:
            if isinstance(item, dict) and item.get("self_ref"):
                by_ref[str(item["self_ref"])] = {"kind": "text", **item}
    if isinstance(tables, list):
        for item in tables:
            if isinstance(item, dict) and item.get("self_ref"):
                by_ref[str(item["self_ref"])] = {"kind": "table", **item}

    ordered: list[dict[str, Any]] = []
    for child in (docling_document.get("body") or {}).get("children", []):
        if not isinstance(child, dict):
            continue
        ref = str(child.get("$ref") or "")
        item = by_ref.get(ref)
        if item is not None:
            ordered.append(item)
    if ordered:
        return ordered
    return list(by_ref.values())


def _build_page_units(*, elements: list[dict[str, Any]], source_name: str) -> list[dict[str, Any]]:
    pages: dict[int, dict[str, Any]] = {}
    for element in elements:
        page_no = _page_no(element)
        if page_no is None:
            continue
        page = pages.setdefault(
            page_no,
            {
                "blocks": [],
                "heading_path": [],
                "page": page_no,
                "parent_id": _parent_id(source_name, "page", page_no),
                "parent_type": "page",
                "source_name": source_name,
                "text_parts": [],
                "title": None,
            },
        )
        text = _element_text(element)
        if not text:
            continue
        if element.get("label") == "section_header" and not page["title"]:
            page["title"] = text
        page["blocks"].append(_block_metadata(element, text))
        page["text_parts"].append(text)

    result: list[dict[str, Any]] = []
    for page_no in sorted(pages):
        page = pages[page_no]
        text = "\n\n".join(page.pop("text_parts")).strip()
        page["text"] = text
        page["char_count"] = len(text)
        page["token_count"] = _count_tokens(text)
        result.append(page)
    return result


def _build_chapter_units(
    *,
    elements: list[dict[str, Any]],
    max_chapter_tokens: int,
    pages: list[dict[str, Any]],
    source_name: str,
) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    heading_stack: list[tuple[int, str]] = []

    def flush() -> None:
        nonlocal current
        if current is not None and current["text_parts"]:
            chapters.append(current)
        current = None

    for element in elements:
        text = _element_text(element)
        if not text:
            continue
        label = str(element.get("label") or "")
        if label == "section_header":
            level = int(element.get("level") or 1)
            heading_stack = [(item_level, title) for item_level, title in heading_stack if item_level < level]
            heading_stack.append((level, text))
            flush()
            current = {
                "blocks": [],
                "heading_path": [title for _, title in heading_stack],
                "page_start": _page_no(element),
                "page_end": _page_no(element),
                "parent_type": "chapter",
                "source_name": source_name,
                "text_parts": [text],
                "title": text,
            }
            current["parent_id"] = _parent_id(source_name, "chapter", len(chapters) + 1)
            current["blocks"].append(_block_metadata(element, text))
            continue
        if current is None:
            current = {
                "blocks": [],
                "heading_path": [],
                "page_start": _page_no(element),
                "page_end": _page_no(element),
                "parent_id": _parent_id(source_name, "chapter", len(chapters) + 1),
                "parent_type": "chapter",
                "source_name": source_name,
                "text_parts": [],
                "title": None,
            }
        page_no = _page_no(element)
        if page_no is not None:
            current["page_start"] = page_no if current["page_start"] is None else min(current["page_start"], page_no)
            current["page_end"] = page_no if current["page_end"] is None else max(current["page_end"], page_no)
        current["blocks"].append(_block_metadata(element, text))
        current["text_parts"].append(text)

    flush()
    normalized: list[dict[str, Any]] = []
    pages_by_number = {int(page["page"]): page for page in pages}
    for chapter in chapters:
        text = "\n\n".join(chapter.pop("text_parts")).strip()
        token_count = _count_tokens(text)
        if token_count > max_chapter_tokens > 0:
            for page_no in range(int(chapter.get("page_start") or 0), int(chapter.get("page_end") or 0) + 1):
                page = pages_by_number.get(page_no)
                if page is None:
                    continue
                fallback = dict(page)
                fallback["fallback_reason"] = "max_chapter_tokens_exceeded"
                fallback["fallback_source_parent_id"] = chapter["parent_id"]
                fallback["parent_id"] = f"{chapter['parent_id']}_page_{page_no:04d}"
                fallback["parent_type"] = "page_fallback"
                normalized.append(fallback)
            continue
        chapter["text"] = text
        chapter["char_count"] = len(text)
        chapter["token_count"] = token_count
        normalized.append(chapter)
    if normalized:
        return normalized
    return [dict(page, parent_type="page_fallback") for page in pages]


def _element_text(element: dict[str, Any]) -> str:
    if element.get("kind") == "table":
        return _table_to_markdown(element)
    return str(element.get("text") or element.get("orig") or "").strip()


def _table_to_markdown(table: dict[str, Any]) -> str:
    grid = (table.get("data") or {}).get("grid")
    if not isinstance(grid, list) or not grid:
        return ""
    rows: list[list[str]] = []
    for raw_row in grid:
        if not isinstance(raw_row, list):
            continue
        row: list[str] = []
        seen: set[tuple[Any, Any, Any, Any]] = set()
        for cell in raw_row:
            if not isinstance(cell, dict):
                continue
            identity = (
                cell.get("start_row_offset_idx"),
                cell.get("end_row_offset_idx"),
                cell.get("start_col_offset_idx"),
                cell.get("end_col_offset_idx"),
            )
            if identity in seen:
                continue
            seen.add(identity)
            row.append(str(cell.get("text") or "").replace("\n", " ").strip())
        if any(row):
            rows.append(row)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    header = padded[0]
    separator = ["---"] * width
    body = padded[1:]
    return "\n".join(
        ["| " + " | ".join(header) + " |", "| " + " | ".join(separator) + " |"]
        + ["| " + " | ".join(row) + " |" for row in body]
    )


def _block_metadata(element: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "char_count": len(text),
        "label": element.get("label"),
        "page": _page_no(element),
        "self_ref": element.get("self_ref"),
        "type": element.get("kind"),
    }


def _page_no(element: dict[str, Any]) -> int | None:
    prov = element.get("prov")
    if isinstance(prov, list) and prov:
        page_no = prov[0].get("page_no") if isinstance(prov[0], dict) else None
        if isinstance(page_no, int):
            return page_no
    return None


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    return "".join(f"{stable_json_dumps(record)}\n" for record in records).encode("utf-8")


def _count_tokens(text: str) -> int:
    return len([token for token in text.split() if token.strip(TOKEN_PATTERN_CHARS)])


def _parent_id(source_name: str, parent_type: str, index: int) -> str:
    safe = "".join(char.lower() if char.isalnum() else "_" for char in Path(source_name).stem)
    safe = "_".join(part for part in safe.split("_") if part) or "document"
    return f"{safe}_{parent_type}_{index:04d}"
