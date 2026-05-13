from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import fitz
import httpx

from app.core.config import get_settings


def list_preparation_methods() -> list[dict[str, Any]]:
    settings = get_settings()
    return [
        {
            "description": "CPU text extraction for PDFs with extractable text layers, plus text and Markdown inputs.",
            "fields": [
                {
                    "default": True,
                    "help_text": "Insert Markdown page headings for PDF pages.",
                    "label": "Page breaks",
                    "name": "page_breaks",
                    "type": "boolean",
                }
            ],
            "id": "pymupdf_text",
            "label": "PyMuPDF text",
            "output_formats": ["markdown"],
        },
        {
            "description": "Convert source files through an external Docling Serve endpoint and store Markdown plus Docling JSON.",
            "fields": [
                {
                    "default": True,
                    "help_text": "Ask Docling to use OCR where applicable.",
                    "label": "OCR",
                    "name": "do_ocr",
                    "type": "boolean",
                },
                {
                    "default": False,
                    "help_text": "Force OCR even when text may already be present.",
                    "label": "Force OCR",
                    "name": "force_ocr",
                    "type": "boolean",
                },
                {
                    "default": "placeholder",
                    "help_text": "Use placeholder for compact RAG-friendly Markdown, or embedded for base64 inline images.",
                    "label": "Image export mode",
                    "name": "image_export_mode",
                    "options": [
                        {"label": "Placeholder", "value": "placeholder"},
                        {"label": "Embedded", "value": "embedded"},
                    ],
                    "type": "select",
                },
                {
                    "default": settings.docling_base_url,
                    "help_text": "Docling Serve base URL. Use a local CPU service or a remote GPU service.",
                    "label": "Base URL",
                    "name": "base_url",
                    "type": "text",
                },
            ],
            "id": "docling",
            "label": "Docling",
            "output_formats": ["markdown", "json"],
        },
    ]


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


def prepare_docling(
    *,
    source_storage_path: str,
    source_manifest: dict[str, Any],
    base_url: str | None = None,
    do_ocr: bool = True,
    force_ocr: bool = False,
    image_export_mode: str = "placeholder",
) -> list[dict[str, Any]]:
    settings = get_settings()
    service_base_url = base_url or settings.docling_base_url
    prepared_files: list[dict[str, Any]] = []

    with httpx.Client(timeout=settings.docling_timeout_seconds) as client:
        for file_entry in source_manifest.get("files", []):
            stored_path = file_entry.get("stored_path")
            if not isinstance(stored_path, str):
                continue

            original_name = str(file_entry.get("original_name") or "source")
            source_path = Path(source_storage_path) / stored_path
            if not source_path.exists():
                raise ValueError(f"Source file is missing from storage: {original_name}")

            document = _convert_with_docling_async(
                client=client,
                base_url=service_base_url,
                path=source_path,
                original_name=original_name,
                do_ocr=do_ocr,
                force_ocr=force_ocr,
                image_export_mode=image_export_mode,
            )
            stem = Path(original_name).stem or "document"
            source = {
                "original_name": original_name,
                "stored_path": stored_path,
            }

            markdown = document.get("md_content") or document.get("markdown")
            if isinstance(markdown, str) and markdown.strip():
                prepared_files.append(
                    {
                        "content": _ensure_trailing_newline(markdown).encode("utf-8"),
                        "content_type": "text/markdown",
                        "original_name": f"{stem}.md",
                        "role": "prepared_markdown",
                        "source": source,
                    }
                )

            json_content = document.get("json_content") or document.get("json")
            if json_content is not None:
                prepared_files.append(
                    {
                        "content": (
                            json.dumps(json_content, ensure_ascii=False, indent=2, sort_keys=True)
                            + "\n"
                        ).encode("utf-8"),
                        "content_type": "application/json",
                        "original_name": f"{stem}.docling.json",
                        "role": "docling_document_json",
                        "source": source,
                    }
                )

    if not prepared_files:
        raise ValueError("Docling did not return supported Markdown or JSON output")

    return prepared_files


def _convert_with_docling_async(
    *,
    client: httpx.Client,
    base_url: str,
    path: Path,
    original_name: str,
    do_ocr: bool,
    force_ocr: bool,
    image_export_mode: str,
) -> dict[str, Any]:
    request_payload = {
        "options": {
            "document_timeout": int(get_settings().docling_async_max_wait_seconds),
            "do_ocr": do_ocr,
            "force_ocr": force_ocr,
            "image_export_mode": image_export_mode,
            "to_formats": ["md", "json"],
        },
        "sources": [
            {
                "base64_string": base64.b64encode(path.read_bytes()).decode("ascii"),
                "filename": original_name,
                "kind": "file",
            }
        ],
    }
    try:
        response = client.post(_docling_convert_async_url(base_url), json=request_payload)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise ValueError(f"Docling async submit failed for {original_name}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Docling returned non-JSON response for {original_name}") from exc

    task_id = payload.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return _extract_docling_document(payload, original_name)

    result_payload = _wait_docling_task(
        client=client,
        base_url=base_url,
        original_name=original_name,
        task_id=task_id,
    )
    return _extract_docling_document(result_payload, original_name)


def _wait_docling_task(
    *,
    client: httpx.Client,
    base_url: str,
    original_name: str,
    task_id: str,
) -> dict[str, Any]:
    settings = get_settings()
    deadline = time.monotonic() + settings.docling_async_max_wait_seconds
    last_status: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            response = client.get(_docling_status_url(base_url, task_id))
            response.raise_for_status()
            last_status = response.json()
        except httpx.HTTPError as exc:
            raise ValueError(f"Docling status request failed for {original_name}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"Docling returned non-JSON status for {original_name}") from exc

        task_status = str(
            last_status.get("task_status")
            or last_status.get("status")
            or last_status.get("state")
            or ""
        ).lower()
        if task_status in {"success", "succeeded", "completed", "done"}:
            return _fetch_docling_result(client, base_url, original_name, task_id)
        if task_status in {"failure", "failed", "error"}:
            raise ValueError(f"Docling conversion failed for {original_name}: {last_status}")
        time.sleep(max(0.2, settings.docling_poll_interval_seconds))

    raise ValueError(
        f"Docling conversion timed out for {original_name} after "
        f"{settings.docling_async_max_wait_seconds:g} seconds. Last status: {last_status}"
    )


def _fetch_docling_result(
    client: httpx.Client,
    base_url: str,
    original_name: str,
    task_id: str,
) -> dict[str, Any]:
    try:
        response = client.get(_docling_result_url(base_url, task_id))
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise ValueError(f"Docling result request failed for {original_name}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Docling returned non-JSON result for {original_name}") from exc


def _extract_docling_document(payload: dict[str, Any], original_name: str) -> dict[str, Any]:
    errors = payload.get("errors")
    if errors:
        raise ValueError(f"Docling conversion failed for {original_name}: {errors}")

    document = payload.get("document")
    if isinstance(document, dict):
        return document

    documents = payload.get("documents")
    if isinstance(documents, list) and documents and isinstance(documents[0], dict):
        return documents[0]

    raise ValueError(f"Docling response did not include a document for {original_name}")


def _docling_convert_async_url(base_url: str) -> str:
    return f"{_docling_v1_url(base_url)}/convert/source/async"


def _docling_status_url(base_url: str, task_id: str) -> str:
    return f"{_docling_v1_url(base_url)}/status/poll/{task_id}"


def _docling_result_url(base_url: str, task_id: str) -> str:
    return f"{_docling_v1_url(base_url)}/result/{task_id}"


def _docling_v1_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


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


def _ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else f"{text}\n"
