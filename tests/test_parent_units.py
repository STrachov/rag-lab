import json

from app.services.chunking import ChunkingParams, chunk_prepared_asset
from app.services.hashing import stable_json_dumps
from app.services.parent_units import build_docling_parent_unit_files
from app.services.runtime_cache import _parent_retrieval_results


def test_build_docling_parent_units_pages_and_chapter_fallback() -> None:
    document = _docling_document()

    files = build_docling_parent_unit_files(
        docling_document=document,
        max_chapter_tokens=5,
        source_name="policy.pdf",
        stem="policy",
    )

    by_name = {item["original_name"]: item for item in files}
    pages = _jsonl(by_name["policy.pages.jsonl"]["content"])
    chapters = _jsonl(by_name["policy.chapters.jsonl"]["content"])

    assert [page["page"] for page in pages] == [1, 2]
    assert pages[0]["parent_type"] == "page"
    assert "Introduction" in pages[0]["text"]
    assert chapters[0]["parent_type"] == "page_fallback"
    assert chapters[0]["fallback_reason"] == "max_chapter_tokens_exceeded"


def test_page_and_chapter_recursive_chunk_from_parent_jsonl(tmp_path) -> None:
    document = _docling_document()
    files = build_docling_parent_unit_files(
        docling_document=document,
        max_chapter_tokens=100,
        source_name="policy.pdf",
        stem="policy",
    )
    base_dir = tmp_path / "prepared"
    files_dir = base_dir / "files"
    files_dir.mkdir(parents=True)
    manifest_files = []
    for index, item in enumerate(files, start=1):
        stored_name = f"f_{index:06d}.jsonl"
        (files_dir / stored_name).write_bytes(item["content"])
        manifest_files.append(
            {
                "content_type": item["content_type"],
                "original_name": item["original_name"],
                "role": item["role"],
                "stored_path": f"files/{stored_name}",
            }
        )
    manifest = {"files": manifest_files}

    page_chunks = chunk_prepared_asset(
        storage_path=str(base_dir),
        manifest_json=manifest,
        chunking=ChunkingParams(strategy="page_recursive", params={"chunk_size": 8, "chunk_overlap": 0}),
    )["chunks"]
    chapter_chunks = chunk_prepared_asset(
        storage_path=str(base_dir),
        manifest_json=manifest,
        chunking=ChunkingParams(strategy="chapter_recursive", params={"chunk_size": 8, "chunk_overlap": 0}),
    )["chunks"]

    assert page_chunks[0]["parent_type"] == "page"
    assert page_chunks[0]["parent_id"].endswith("page_0001")
    assert chapter_chunks[0]["parent_type"] == "chapter"
    assert chapter_chunks[0]["parent_id"].endswith("chapter_0001")


def test_parent_retrieval_groups_chunks_by_parent(monkeypatch, tmp_path) -> None:
    chunks_dir = tmp_path / "cache" / "chunks" / "chunks_key"
    chunks_dir.mkdir(parents=True)
    chunks = [
        {
            "chunk_id": "chunk_000001",
            "parent_id": "policy_page_0001",
            "parent_text": "Full parent page text.",
            "parent_token_count": 4,
            "parent_type": "page",
            "source_name": "policy.pdf",
            "text": "Full parent",
        },
        {
            "chunk_id": "chunk_000002",
            "parent_id": "policy_page_0001",
            "parent_text": "Full parent page text.",
            "parent_token_count": 4,
            "parent_type": "page",
            "source_name": "policy.pdf",
            "text": "page text",
        },
    ]
    (chunks_dir / "chunks.jsonl").write_text(
        "".join(f"{stable_json_dumps(chunk)}\n" for chunk in chunks),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.runtime_cache.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )

    grouped = _parent_retrieval_results(
        chunks=[
            {"chunk_id": "chunk_000001", "score": 0.2},
            {"chunk_id": "chunk_000002", "score": 0.7},
        ],
        index_metadata={"chunks_cache_key": "chunks_key"},
        parent_score="max",
        parent_type="page",
    )

    assert len(grouped) == 1
    assert grouped[0]["chunk_id"] == "policy_page_0001"
    assert grouped[0]["score"] == 0.7
    assert grouped[0]["text_preview"] == "Full parent page text."
    assert [item["chunk_id"] for item in grouped[0]["evidence_chunks"]] == [
        "chunk_000001",
        "chunk_000002",
    ]


def _jsonl(content: bytes) -> list[dict]:
    return [json.loads(line) for line in content.decode("utf-8").splitlines()]


def _docling_document() -> dict:
    return {
        "body": {
            "children": [
                {"$ref": "#/texts/0"},
                {"$ref": "#/texts/1"},
                {"$ref": "#/texts/2"},
            ]
        },
        "texts": [
            {
                "label": "section_header",
                "level": 1,
                "prov": [{"page_no": 1}],
                "self_ref": "#/texts/0",
                "text": "Introduction",
            },
            {
                "label": "text",
                "prov": [{"page_no": 1}],
                "self_ref": "#/texts/1",
                "text": "Alpha beta gamma delta epsilon zeta eta theta.",
            },
            {
                "label": "text",
                "prov": [{"page_no": 2}],
                "self_ref": "#/texts/2",
                "text": "Iota kappa lambda mu nu xi omicron pi.",
            },
        ],
    }
