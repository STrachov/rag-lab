from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz


def prepare_pymupdf_text(
    *,
    source_storage_path: str,
    source_manifest: dict[str, Any],
    page_breaks: bool = True,
) -> list[dict[str, Any]]:
    prepared_files: list[dict[str, Any]] = []
    for file_entry in source_manifest.get("files", []):
        stored_path = file_entry.get("stored_path")
        if not isinstance(stored_path, str):
            continue

        file_type = (file_entry.get("inspection") or {}).get("file_type")
        original_name = str(file_entry.get("original_name") or "source")
        source_path = Path(source_storage_path) / stored_path

        if file_type == "pdf" or original_name.lower().endswith(".pdf"):
            markdown = _pdf_to_markdown(source_path, original_name, page_breaks=page_breaks)
        elif file_type in {"markdown", "text"} or original_name.lower().endswith((".md", ".txt")):
            markdown = _text_file_to_markdown(source_path, original_name)
        else:
            continue

        prepared_name = f"{Path(original_name).stem}.md"
        prepared_files.append(
            {
                "content": markdown.encode("utf-8"),
                "content_type": "text/markdown",
                "original_name": prepared_name,
                "source": {
                    "original_name": original_name,
                    "stored_path": stored_path,
                },
            }
        )

    if not prepared_files:
        raise ValueError("No supported source files were found for pymupdf_text preparation")

    return prepared_files


def _pdf_to_markdown(path: Path, original_name: str, *, page_breaks: bool) -> str:
    doc = fitz.open(path)
    try:
        if doc.is_encrypted:
            raise ValueError(f"{original_name} is encrypted and cannot be prepared")

        sections = [f"# {original_name}", ""]
        total_chars = 0
        for index, page in enumerate(doc, start=1):
            text = (page.get_text("text") or "").strip()
            total_chars += len(text)
            if page_breaks:
                sections.extend([f"## Page {index}", ""])
            if text:
                sections.extend([text, ""])

        if total_chars == 0:
            raise ValueError(f"{original_name} has no extractable text layer")

        return "\n".join(sections).strip() + "\n"
    finally:
        doc.close()


def _text_file_to_markdown(path: Path, original_name: str) -> str:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if original_name.lower().endswith(".md"):
        return text + "\n"
    return f"# {original_name}\n\n{text}\n"
