from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz


def inspect_file(path: Path, *, content_type: str | None, original_name: str) -> dict[str, Any]:
    if _looks_like_pdf(path, content_type, original_name):
        return _inspect_pdf(path)

    return {
        "file_type": _infer_file_type(path, content_type, original_name),
        "status": "skipped",
        "reason": "No lightweight inspector is available for this file type.",
    }


def _inspect_pdf(path: Path) -> dict[str, Any]:
    try:
        doc = fitz.open(path)
    except Exception as exc:
        return {
            "file_type": "pdf",
            "status": "failed",
            "error": str(exc),
        }

    try:
        metadata = _clean_metadata(doc.metadata or {})
        page_count = doc.page_count
        is_encrypted = bool(doc.is_encrypted)

        if is_encrypted:
            return {
                "file_type": "pdf",
                "is_encrypted": True,
                "metadata": metadata,
                "page_count": page_count,
                "scan_likelihood": {
                    "likely_scanned": None,
                    "reason": "Encrypted PDF cannot be inspected without unlocking.",
                },
                "status": "ok",
                "text_layer": {
                    "avg_text_chars_per_page": 0,
                    "has_text": False,
                    "pages_with_text": 0,
                    "text_char_count": 0,
                    "text_pages_ratio": 0,
                },
            }

        text_char_count = 0
        pages_with_text = 0
        image_count = 0
        pages_with_images = 0

        for page in doc:
            text = page.get_text("text") or ""
            normalized_text_length = len(text.strip())
            if normalized_text_length > 0:
                pages_with_text += 1
                text_char_count += normalized_text_length

            page_image_count = len(page.get_images(full=True))
            if page_image_count > 0:
                pages_with_images += 1
                image_count += page_image_count

        text_pages_ratio = pages_with_text / page_count if page_count else 0
        avg_text_chars_per_page = text_char_count / page_count if page_count else 0
        likely_scanned = text_pages_ratio < 0.2 and pages_with_images > 0

        return {
            "file_type": "pdf",
            "images": {
                "image_count": image_count,
                "pages_with_images": pages_with_images,
            },
            "is_encrypted": False,
            "metadata": metadata,
            "page_count": page_count,
            "scan_likelihood": {
                "likely_scanned": likely_scanned,
                "reason": _scan_reason(likely_scanned, text_pages_ratio, pages_with_images),
            },
            "status": "ok",
            "text_layer": {
                "avg_text_chars_per_page": round(avg_text_chars_per_page, 2),
                "has_text": text_char_count > 0,
                "pages_with_text": pages_with_text,
                "text_char_count": text_char_count,
                "text_pages_ratio": round(text_pages_ratio, 4),
            },
        }
    except Exception as exc:
        return {
            "file_type": "pdf",
            "status": "failed",
            "error": str(exc),
        }
    finally:
        doc.close()


def _looks_like_pdf(path: Path, content_type: str | None, original_name: str) -> bool:
    return (
        path.suffix.lower() == ".pdf"
        or original_name.lower().endswith(".pdf")
        or content_type == "application/pdf"
    )


def _infer_file_type(path: Path, content_type: str | None, original_name: str) -> str:
    suffix = Path(original_name).suffix.lower() or path.suffix.lower()
    if suffix == ".md":
        return "markdown"
    if suffix == ".txt":
        return "text"
    if suffix == ".docx":
        return "docx"
    if suffix in (".html", ".htm"):
        return "html"
    if suffix:
        return suffix.removeprefix(".")
    if content_type:
        return content_type
    return "unknown"


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    allowed = ("title", "author", "subject", "keywords", "creator", "producer", "creationDate", "modDate")
    return {
        key: value
        for key, value in metadata.items()
        if key in allowed and isinstance(value, str) and value.strip()
    }


def _scan_reason(likely_scanned: bool, text_pages_ratio: float, pages_with_images: int) -> str:
    if likely_scanned:
        return "Few pages contain extractable text and images are present."
    if text_pages_ratio >= 0.8:
        return "Most pages contain extractable text."
    if pages_with_images > 0:
        return "Document has mixed text and images."
    return "No strong scan signal detected."
