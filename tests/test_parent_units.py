import json
import hashlib

import pytest

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
                "sha256": hashlib.sha256(item["content"]).hexdigest(),
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


def _nested_cover_document():
    # Synthetic content with Docling's real body -> form_area -> item shape.
    values = [
        ("section_header", "UNITED STATES SECURITIES AND EXCHANGE COMMISSION", 1),
        ("title", "FORM 10-K", 1),
        ("text", "WHEELER REAL ESTATE INVESTMENT TRUST, INC.", 1),
        ("unfamiliar_form_field", "45-2681082", 1),
        ("list_item", "Cover list entry", 1),
        ("caption", "Securities caption", 1),
        (None, "Indicate by check mark whether the registrant is a large accelerated filer", 1),
        ("section_header", "Second page section", 2),
        ("text", "Second page body", 2),
    ]
    texts = [{"self_ref": f"#/texts/{i}", "text": text, "label": label,
              "prov": [{"page_no": page}]} for i, (label, text, page) in enumerate(values)]
    texts[8]["prov"] = [{}, {"page_no": 2}]  # No bbox is required; inspect all provenance entries.
    table = {"self_ref": "#/tables/0", "label": "table", "prov": [{"page_no": 1}],
             "captions": [{"$ref": "#/texts/5"}],
             "data": {"grid": [[{"text": symbol, "start_row_offset_idx": 0,
                 "end_row_offset_idx": 1, "start_col_offset_idx": i, "end_col_offset_idx": i + 1}
                 for i, symbol in enumerate(["WHLR", "WHLRP", "WHLRD", "WHLRL"])]]}}
    return {
        "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/groups/0"},
                               {"$ref": "#/texts/6"}, {"$ref": "#/texts/7"}, {"$ref": "#/texts/8"}]},
        "groups": [
            {"self_ref": "#/groups/0", "label": "form_area", "children": [
                {"$ref": "#/texts/1"}, {"$ref": "#/groups/1"}, {"$ref": "#/tables/0"}]},
            {"self_ref": "#/groups/1", "label": "key_value_area", "children": [
                {"$ref": f"#/texts/{i}"} for i in [2, 3, 4]]},
        ],
        "texts": texts, "tables": [table],
    }


def test_nested_cover_content_survives_pages_and_chapters():
    document = _nested_cover_document()
    files = build_docling_parent_unit_files(docling_document=document, max_chapter_tokens=10000,
                                           source_name="cover.pdf", stem="cover")
    pages = _jsonl(files[0]["content"])
    chapters = _jsonl(files[1]["content"])
    markers = ["UNITED STATES", "FORM 10-K", "WHEELER REAL ESTATE INVESTMENT TRUST, INC.",
               "45-2681082", "Cover list entry", "WHLRP", "Securities caption", "Indicate by check mark"]
    for text in [pages[0]["text"], "\n".join(c["text"] for c in chapters)]:
        positions = [text.index(marker) for marker in markers]
        assert positions == sorted(positions)
        assert text.count("Indicate by check mark") == 1
    assert pages[0]["page"] == 1
    assert pages[0]["parent_id"] == "cover_page_0001"
    assert pages[1]["page"] == 2
    assert "Second page body" in pages[1]["text"]
    assert "Second page body" not in pages[0]["text"]
    assert all(c["page_start"] == c["page_end"] == 1 for c in chapters if "WHLRP" in c["text"])


def test_docling_walk_deduplicates_references_not_equal_text():
    document = _nested_cover_document()
    document["body"]["children"].insert(2, {"$ref": "#/texts/4"})
    document["groups"][1]["children"].append({"$ref": "#/groups/0"})  # Defensive cycle guard.
    document["texts"].append({"self_ref": "#/texts/9", "text": "Cover list entry", "prov": [{"page_no": 2}]})
    document["body"]["children"].append({"$ref": "#/texts/9"})
    pages = _jsonl(build_docling_parent_unit_files(docling_document=document, max_chapter_tokens=10000,
                   source_name="cover.pdf", stem="cover")[0]["content"])
    assert pages[0]["text"].count("Cover list entry") == 1
    assert pages[1]["text"].count("Cover list entry") == 1


def test_nested_content_reaches_page_and_chapter_chunking(tmp_path):
    files = build_docling_parent_unit_files(docling_document=_nested_cover_document(),
        max_chapter_tokens=10000, source_name="cover.pdf", stem="cover")
    entries = []
    for file in files:
        (tmp_path / file["original_name"]).write_bytes(file["content"])
        entries.append({**file, "content": None, "stored_path": file["original_name"],
                        "sha256": hashlib.sha256(file["content"]).hexdigest()})
    for strategy in ["page_recursive", "chapter_recursive"]:
        chunks = chunk_prepared_asset(storage_path=str(tmp_path), manifest_json={"files": entries},
                     chunking=ChunkingParams(strategy=strategy, params={"chunk_size": 300, "chunk_overlap": 50}))["chunks"]
        assert any("WHLRP" in c["text"] and c["page"] == 1 for c in chunks)
        assert any("45-2681082" in c["text"] for c in chunks)


def test_content_before_first_section_and_nested_picture_caption():
    document = _nested_cover_document()
    document["texts"][0]["label"] = "title"
    document["pictures"] = [{"self_ref": "#/pictures/0", "children": [{"$ref": "#/texts/5"}]}]
    document["groups"][0]["children"].append({"$ref": "#/pictures/0"})
    files = build_docling_parent_unit_files(docling_document=document, max_chapter_tokens=10000,
                                           source_name="cover.pdf", stem="cover")
    assert _jsonl(files[1]["content"])[0]["text"].startswith("UNITED STATES")
    assert _jsonl(files[0]["content"])[0]["text"].count("Securities caption") == 1


def test_unattributable_text_fails_instead_of_silently_disappearing():
    document = _nested_cover_document()
    document["texts"][2]["prov"] = []
    with pytest.raises(ValueError, match="no page provenance"):
        build_docling_parent_unit_files(docling_document=document, max_chapter_tokens=10000,
                                       source_name="cover.pdf", stem="cover")


def test_docling_preparation_keeps_nested_cover_in_all_representations(tmp_path, monkeypatch):
    from app.services import preparation
    source = b"synthetic source PDF bytes"
    (tmp_path / "cover.pdf").write_bytes(source)
    document = _nested_cover_document()
    def convert(**kwargs):
        assert kwargs["content"] == source
        return {"md_content": "FORM 10-K\n45-2681082\nWHLRP", "json_content": document}
    monkeypatch.setattr(preparation, "_convert_with_docling_async", convert)
    files = preparation.prepare_docling(source_storage_path=str(tmp_path), source_manifest={"files": [{
        "stored_path": "cover.pdf", "original_name": "cover.pdf", "sha256": hashlib.sha256(source).hexdigest(),
    }]})
    by_role = {file["role"]: file for file in files}
    for role in ["prepared_markdown", "prepared_parent_pages", "prepared_parent_chapters"]:
        assert all(marker in by_role[role]["content"].decode() for marker in ["FORM 10-K", "45-2681082", "WHLRP"])
