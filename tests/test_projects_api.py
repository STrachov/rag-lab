from fastapi.testclient import TestClient
import fitz
import httpx
from pathlib import Path

from app.api import projects
from app.services.preparation import prepare_docling


def test_create_project(client: TestClient) -> None:
    response = client.post(
        "/v1/projects",
        json={"name": "Policy RAG", "domain": "policy", "metadata_json": {"owner": "lab"}},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["name"] == "Policy RAG"
    assert body["domain"] == "policy"
    assert body["metadata_json"] == {"owner": "lab"}


def test_list_projects(client: TestClient) -> None:
    client.post("/v1/projects", json={"name": "One"})
    client.post("/v1/projects", json={"name": "Two"})

    response = client.get("/v1/projects")

    assert response.status_code == 200
    names = [project["name"] for project in response.json()["projects"]]
    assert names == ["One", "Two"]


def test_create_data_asset_under_project(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/v1/projects/{project_id}/data-assets",
        json={
            "name": "Raw policies",
            "asset_type": "raw",
            "storage_path": "data/raw/policies",
            "metadata_json": {"source": "synthetic"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project_id
    assert body["name"] == "Raw policies"
    assert body["asset_type"] == "raw"
    assert body["data_format"] == "mixed"
    assert body["storage_kind"] == "uploaded"
    assert body["status"] == "ready"


def test_create_parameter_set_under_project(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/v1/projects/{project_id}/parameter-sets",
        json={
            "name": "Docling hybrid baseline",
            "category": "retrieval",
            "description": "Preparation plus retrieval baseline",
            "params_hash": "sha256:test-params",
            "params_json": {
                "preparation": {"converter": "docling", "settings": {"ocr": False}},
                "retrieval": {"mode": "hybrid", "top_k": 8},
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project_id
    assert body["category"] == "retrieval"
    assert body["params_json"]["preparation"]["converter"] == "docling"


def test_delete_parameter_set_under_project(client: TestClient) -> None:
    project_id = _create_project(client)
    parameter_set_id = _create_parameter_set(client, project_id)

    response = client.delete(f"/v1/projects/{project_id}/parameter-sets/{parameter_set_id}")

    assert response.status_code == 200
    assert response.json()["deleted_parameter_set_id"] == parameter_set_id

    list_response = client.get(f"/v1/projects/{project_id}/parameter-sets")
    assert list_response.status_code == 200
    assert parameter_set_id not in [
        parameter_set["id"] for parameter_set in list_response.json()["parameter_sets"]
    ]


def test_list_chunking_strategies_for_parameters_ui(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.get(f"/v1/projects/{project_id}/parameter-sets/chunking/strategies")

    assert response.status_code == 200
    strategies = response.json()["strategies"]
    strategy_ids = [strategy["id"] for strategy in strategies]
    assert "heading_recursive" in strategy_ids
    assert "recursive" in strategy_ids
    assert "langchain_recursive_character" in strategy_ids
    assert "langchain_markdown_header_recursive" in strategy_ids
    heading_recursive = next(
        strategy for strategy in strategies if strategy["id"] == "heading_recursive"
    )
    field_names = [field["name"] for field in heading_recursive["fields"]]
    assert "chunk_size" in field_names
    assert "preserve_headings" in field_names
    assert heading_recursive["default_params"]["chunk_size"] == 900
    langchain_recursive = next(
        strategy for strategy in strategies if strategy["id"] == "langchain_recursive_character"
    )
    assert "RecursiveCharacterTextSplitter" in langchain_recursive["description"]
    langchain_markdown = next(
        strategy for strategy in strategies if strategy["id"] == "langchain_markdown_header_recursive"
    )
    assert "MarkdownHeaderTextSplitter" in langchain_markdown["description"]
    assert "headers_to_split_on" in [field["name"] for field in langchain_markdown["fields"]]


def test_list_preparation_methods_for_data_ui(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.get(f"/v1/projects/{project_id}/data-assets/preparation/methods")

    assert response.status_code == 200
    methods = response.json()["methods"]
    method_ids = [method["id"] for method in methods]
    assert "pymupdf_text" in method_ids
    assert "docling" in method_ids
    docling = next(method for method in methods if method["id"] == "docling")
    assert docling["output_formats"] == ["markdown", "json"]
    field_names = [field["name"] for field in docling["fields"]]
    assert "do_ocr" in field_names
    assert "force_ocr" in field_names
    image_export_mode = next(field for field in docling["fields"] if field["name"] == "image_export_mode")
    assert image_export_mode["type"] == "select"
    assert [option["value"] for option in image_export_mode["options"]] == ["placeholder", "embedded"]
    assert "base_url" in field_names


def test_list_embedding_models_for_indexing_ui(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.get(f"/v1/projects/{project_id}/embedding/models")

    assert response.status_code == 200
    models = response.json()["models"]
    model_ids = [model["id"] for model in models]
    assert "intfloat_multilingual_e5_small" in model_ids
    assert "baai_bge_small_en_v1_5" in model_ids
    e5 = next(model for model in models if model["id"] == "intfloat_multilingual_e5_small")
    assert e5["provider"] == "sentence_transformers"
    assert e5["model_name"] == "intfloat/multilingual-e5-small"
    assert e5["default_params"]["device"] == "cpu"


def test_list_sparse_models_for_hybrid_indexing_ui(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.get(f"/v1/projects/{project_id}/sparse/models")

    assert response.status_code == 200
    models = response.json()["models"]
    model_ids = [model["id"] for model in models]
    assert "bm25_local" in model_ids
    bm25 = next(model for model in models if model["id"] == "bm25_local")
    assert bm25["provider"] == "rag_lab"
    assert bm25["default_params"]["k1"] == 1.2
    assert bm25["default_params"]["b"] == 0.75
    fields = {field["name"]: field for field in bm25["fields"]}
    assert fields["k1"]["min"] == 0
    assert fields["k1"]["max"] == 4
    assert fields["k1"]["step"] == 0.05
    assert fields["b"]["min"] == 0
    assert fields["b"]["max"] == 1
    assert fields["b"]["step"] == 0.05


def test_materialize_chunks_creates_derived_cache_with_docling_sidecar(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    project_id = _create_project(client)
    raw_asset_id = _create_data_asset(client, project_id)
    _patch_data_dirs(monkeypatch, tmp_path)
    upload_response = client.post(
        f"/v1/projects/{project_id}/data-assets/prepared/upload",
        data={
            "name": "Docling prepared policies",
            "data_format": "mixed",
            "parent_id": raw_asset_id,
            "preparation_params_json": '{"method":"docling","output_format":"markdown_json"}',
        },
        files=[
            ("files", ("policy.md", b"# Policy\n\nPayment is due within 30 days.", "text/markdown")),
            (
                "files",
                (
                    "policy.docling.json",
                    b'{"schema_name":"DoclingDocument"}',
                    "application/json",
                ),
            ),
        ],
    )
    assert upload_response.status_code == 201
    data_asset_id = upload_response.json()["id"]

    response = client.post(
        f"/v1/projects/{project_id}/chunks/materialize",
        json={
            "data_asset_id": data_asset_id,
            "chunking": {
                "strategy": "heading_recursive",
                "params": {
                    "chunk_size": 8,
                    "chunk_overlap": 2,
                    "tokenizer": "cl100k_base",
                    "preserve_headings": True,
                    "preserve_tables": True,
                    "page_boundary_mode": "soft",
                },
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["cache_type"] == "chunks"
    assert body["status"] == "ready"
    metadata = body["metadata_json"]
    assert metadata["schema_version"] == "raglab.chunks.v1"
    assert metadata["summary"]["chunk_count"] >= 1
    assert metadata["sidecar_files"][0]["original_name"] == "policy.docling.json"
    chunks_path = Path(metadata["chunks_path"])
    assert chunks_path.exists()
    first_chunk = chunks_path.read_text(encoding="utf-8").splitlines()[0]
    assert '"chunk_id":"chunk_000001"' in first_chunk
    assert "Payment is due within 30 days" in first_chunk


def test_qdrant_index_and_retrieval_preview_use_cache_contract(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    project_id = _create_project(client)
    data_asset_id = _upload_prepared_data_asset_with_content(
        client,
        monkeypatch,
        tmp_path,
        project_id,
        b"# Policy\n\nPayment is due within 30 days.",
    )
    _patch_data_dirs(monkeypatch, tmp_path)
    chunks_response = client.post(
        f"/v1/projects/{project_id}/chunks/materialize",
        json={
            "data_asset_id": data_asset_id,
            "chunking": {
                "strategy": "heading_recursive",
                "params": {
                    "chunk_size": 8,
                    "chunk_overlap": 2,
                    "tokenizer": "cl100k_base",
                    "preserve_headings": True,
                    "preserve_tables": True,
                    "page_boundary_mode": "soft",
                },
            },
        },
    )
    assert chunks_response.status_code == 201
    chunks_cache_id = chunks_response.json()["id"]
    fake_qdrant = FakeQdrantStore()
    monkeypatch.setattr("app.api.runtime._qdrant_store", lambda: fake_qdrant)
    monkeypatch.setattr("app.services.runtime_cache.create_embedder", fake_create_embedder)

    index_response = client.post(
        f"/v1/projects/{project_id}/indexes/qdrant",
        json={
            "chunks_cache_id": chunks_cache_id,
            "embedding": {
                "model_id": "intfloat_multilingual_e5_small",
                "params": {"batch_size": 4, "device": "cpu", "normalize": True},
            },
        },
    )

    assert index_response.status_code == 201
    index_cache = index_response.json()
    assert index_cache["cache_type"] == "qdrant_index"
    assert index_cache["metadata_json"]["collection_name"].startswith("raglab_qdrant_")
    assert index_cache["metadata_json"]["embedding"]["model"] == "intfloat/multilingual-e5-small"
    assert index_cache["metadata_json"]["index_mode"] == "hybrid"
    assert index_cache["metadata_json"]["sparse"]["model_id"] == "bm25_local"
    assert index_cache["metadata_json"]["sparse_stats_path"]
    assert fake_qdrant.points
    assert "dense" in fake_qdrant.points[0]["vector"]
    assert "sparse" in fake_qdrant.points[0]["vector"]

    cache_response = client.get(
        f"/v1/projects/{project_id}/derived-cache",
        params={"cache_type": "qdrant_index"},
    )
    assert cache_response.status_code == 200
    assert [cache["id"] for cache in cache_response.json()["derived_caches"]] == [index_cache["id"]]

    retrieve_response = client.post(
        f"/v1/projects/{project_id}/retrieve/preview",
        json={
            "index_cache_id": index_cache["id"],
            "mode": "hybrid",
            "query": "When is payment due?",
            "top_k": 1,
        },
    )

    assert retrieve_response.status_code == 200
    retrieved = retrieve_response.json()["retrieved_chunks"]
    assert retrieved[0]["chunk_id"] == "chunk_000001"
    assert retrieved[0]["source_name"] == "policy.md"
    assert retrieved[0]["dense_score"] == 0.99
    assert retrieved[0]["sparse_score"] == 0.88
    assert "Payment is due within 30 days" in retrieved[0]["text_preview"]


def test_qdrant_index_failure_is_visible_in_derived_cache(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    project_id = _create_project(client)
    data_asset_id = _upload_prepared_data_asset_with_content(
        client,
        monkeypatch,
        tmp_path,
        project_id,
        b"# Policy\n\nPayment is due within 30 days.",
    )
    _patch_data_dirs(monkeypatch, tmp_path)
    chunks_response = client.post(
        f"/v1/projects/{project_id}/chunks/materialize",
        json={
            "data_asset_id": data_asset_id,
            "chunking": {
                "strategy": "heading_recursive",
                "params": {
                    "chunk_size": 8,
                    "chunk_overlap": 2,
                    "tokenizer": "cl100k_base",
                    "preserve_headings": True,
                    "preserve_tables": True,
                    "page_boundary_mode": "soft",
                },
            },
        },
    )
    assert chunks_response.status_code == 201
    chunks_cache_id = chunks_response.json()["id"]
    monkeypatch.setattr("app.api.runtime._qdrant_store", lambda: FailingQdrantStore())
    monkeypatch.setattr("app.services.runtime_cache.create_embedder", fake_create_embedder)

    index_response = client.post(
        f"/v1/projects/{project_id}/indexes/qdrant",
        json={
            "chunks_cache_id": chunks_cache_id,
            "embedding": {
                "model_id": "intfloat_multilingual_e5_small",
                "params": {"batch_size": 4, "device": "cpu", "normalize": True},
            },
        },
    )

    assert index_response.status_code == 502
    assert "Qdrant is unavailable" in index_response.json()["detail"]

    cache_response = client.get(
        f"/v1/projects/{project_id}/derived-cache",
        params={"cache_type": "qdrant_index"},
    )
    assert cache_response.status_code == 200
    caches = cache_response.json()["derived_caches"]
    assert len(caches) == 1
    assert caches[0]["status"] == "failed"
    assert caches[0]["metadata_json"]["error_json"]["message"] == "Qdrant is unavailable"
    assert caches[0]["metadata_json"]["collection_name"].startswith("raglab_qdrant_")


def test_preview_chunking_for_prepared_markdown(client: TestClient, monkeypatch, tmp_path) -> None:
    project_id = _create_project(client)
    data_asset_id = _upload_prepared_data_asset_with_content(
        client,
        monkeypatch,
        tmp_path,
        project_id,
        b"# Policy\n\n## Page 1\n\nPayment is due within 30 days.\n\n## Page 2\n\nRefunds need approval.",
    )

    response = client.post(
        f"/v1/projects/{project_id}/parameter-sets/chunking/preview",
        json={
            "data_asset_id": data_asset_id,
            "chunking": {
                "strategy": "heading_recursive",
                "params": {
                    "chunk_size": 8,
                    "chunk_overlap": 2,
                    "tokenizer": "cl100k_base",
                    "preserve_headings": True,
                    "preserve_tables": True,
                    "page_boundary_mode": "soft",
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["strategy"] == "heading_recursive"
    assert body["summary"]["files_count"] == 1
    assert body["summary"]["chunk_count"] >= 2
    assert body["summary"]["chunks_by_file"] == [
        {"source_name": "policy.md", "chunk_count": body["summary"]["chunk_count"]}
    ]
    assert body["chunks"][0]["chunk_id"] == "preview_000001"
    assert body["chunks"][0]["source_name"] == "policy.md"
    assert body["chunks"][0]["heading_path"]
    assert "Payment" in " ".join(chunk["text_preview"] for chunk in body["chunks"])


def test_preview_langchain_recursive_character_chunking(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    project_id = _create_project(client)
    data_asset_id = _upload_prepared_data_asset_with_content(
        client,
        monkeypatch,
        tmp_path,
        project_id,
        b"Alpha beta gamma.\n\nDelta epsilon zeta.\n\nEta theta iota.",
    )

    response = client.post(
        f"/v1/projects/{project_id}/parameter-sets/chunking/preview",
        json={
            "data_asset_id": data_asset_id,
            "chunking": {
                "strategy": "langchain_recursive_character",
                "params": {
                    "chunk_size": 24,
                    "chunk_overlap": 4,
                    "separators": "\\n\\n|\\n| |",
                    "keep_separator": True,
                    "is_separator_regex": False,
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["strategy"] == "langchain_recursive_character"
    assert body["summary"]["chunk_count"] >= 2
    assert body["chunks"][0]["source_name"] == "policy.md"
    assert "Alpha" in body["chunks"][0]["text_preview"]


def test_preview_langchain_markdown_header_recursive_chunking(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    project_id = _create_project(client)
    data_asset_id = _upload_prepared_data_asset_with_content(
        client,
        monkeypatch,
        tmp_path,
        project_id,
        b"# Policy\n\n## Payment\n\nPayment is due within 30 days.\n\n## Refunds\n\nRefunds need approval.",
    )

    response = client.post(
        f"/v1/projects/{project_id}/parameter-sets/chunking/preview",
        json={
            "data_asset_id": data_asset_id,
            "chunking": {
                "strategy": "langchain_markdown_header_recursive",
                "params": {
                    "headers_to_split_on": "#:h1|##:h2|###:h3",
                    "strip_headers": False,
                    "chunk_size": 48,
                    "chunk_overlap": 4,
                    "separators": "\\n\\n|\\n| |",
                    "keep_separator": True,
                    "is_separator_regex": False,
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["strategy"] == "langchain_markdown_header_recursive"
    assert body["summary"]["chunk_count"] >= 2
    heading_paths = [chunk["heading_path"] for chunk in body["chunks"]]
    assert ["Policy", "Payment"] in heading_paths
    assert any(chunk["section"] == "Refunds" for chunk in body["chunks"])


def test_preview_chunking_requires_prepared_asset(client: TestClient) -> None:
    project_id = _create_project(client)
    raw_asset_id = _create_data_asset(client, project_id)

    response = client.post(
        f"/v1/projects/{project_id}/parameter-sets/chunking/preview",
        json={
            "data_asset_id": raw_asset_id,
            "chunking": {"strategy": "heading_recursive", "params": {"chunk_size": 900}},
        },
    )

    assert response.status_code == 400
    assert "prepared" in response.json()["detail"]


def test_preview_chunking_rejects_overlap_at_or_above_size(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    project_id = _create_project(client)
    data_asset_id = _upload_prepared_data_asset(client, monkeypatch, tmp_path, project_id)

    response = client.post(
        f"/v1/projects/{project_id}/parameter-sets/chunking/preview",
        json={
            "data_asset_id": data_asset_id,
            "chunking": {
                "strategy": "heading_recursive",
                "params": {"chunk_size": 100, "chunk_overlap": 100},
            },
        },
    )

    assert response.status_code == 400
    assert "chunk_overlap" in response.json()["detail"]


def test_preview_chunking_rejects_flat_params_payload(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    project_id = _create_project(client)
    data_asset_id = _upload_prepared_data_asset(client, monkeypatch, tmp_path, project_id)

    response = client.post(
        f"/v1/projects/{project_id}/parameter-sets/chunking/preview",
        json={
            "data_asset_id": data_asset_id,
            "chunking": {"strategy": "heading_recursive", "chunk_size": 100},
        },
    )

    assert response.status_code == 422


def test_upload_raw_data_asset(client: TestClient, monkeypatch, tmp_path) -> None:
    project_id = _create_project(client)
    monkeypatch.setattr(
        "app.services.data_assets.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )

    response = client.post(
        f"/v1/projects/{project_id}/data-assets/raw/upload",
        data={"name": "Raw PDF", "data_format": "pdf"},
        files={"files": ("policy.pdf", b"synthetic pdf bytes", "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["asset_type"] == "raw"
    assert body["data_format"] == "pdf"
    assert body["manifest_hash"].startswith("sha256:")
    assert body["current_manifest_json"]["files"][0]["original_name"] == "policy.pdf"
    assert body["current_manifest_json"]["files"][0]["stored_path"] == "files/f_000001.pdf"


def test_upload_pdf_source_inspects_text_layer(client: TestClient, monkeypatch, tmp_path) -> None:
    project_id = _create_project(client)
    monkeypatch.setattr(
        "app.services.data_assets.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )
    pdf_bytes = _make_text_pdf_bytes("Synthetic text layer")

    response = client.post(
        f"/v1/projects/{project_id}/data-assets/raw/upload",
        data={"name": "Text PDF", "data_format": "pdf"},
        files={"files": ("text.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 201
    inspection = response.json()["current_manifest_json"]["files"][0]["inspection"]
    assert inspection["status"] == "ok"
    assert inspection["file_type"] == "pdf"
    assert inspection["page_count"] == 1
    assert inspection["text_layer"]["has_text"] is True
    assert inspection["scan_likelihood"]["likely_scanned"] is False


def test_download_data_asset_file_uses_original_filename(client: TestClient, monkeypatch, tmp_path) -> None:
    project_id = _create_project(client)
    monkeypatch.setattr(
        "app.services.data_assets.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )

    upload_response = client.post(
        f"/v1/projects/{project_id}/data-assets/raw/upload",
        data={"name": "Raw PDF", "data_format": "pdf"},
        files={"files": ("policy.pdf", b"download me", "application/pdf")},
    )
    assert upload_response.status_code == 201
    asset = upload_response.json()

    download_response = client.get(
        f"/v1/projects/{project_id}/data-assets/{asset['id']}/files/download",
        params={"stored_path": "files/f_000001.pdf"},
    )

    assert download_response.status_code == 200
    assert download_response.content == b"download me"
    assert 'filename="policy.pdf"' in download_response.headers["content-disposition"]


def test_prepare_source_asset_with_pymupdf_text(client: TestClient, monkeypatch, tmp_path) -> None:
    project_id = _create_project(client)
    monkeypatch.setattr(
        "app.services.data_assets.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )
    pdf_bytes = _make_text_pdf_bytes("Payment is due within 30 days.")
    upload_response = client.post(
        f"/v1/projects/{project_id}/data-assets/raw/upload",
        data={"name": "Policy PDF", "data_format": "pdf"},
        files={"files": ("policy.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_response.status_code == 201
    source_asset = upload_response.json()

    prepare_response = client.post(
        f"/v1/projects/{project_id}/data-assets/{source_asset['id']}/prepare",
        json={"method": "pymupdf_text", "settings": {"page_breaks": True}},
    )

    assert prepare_response.status_code == 201
    prepared = prepare_response.json()
    assert prepared["asset_type"] == "prepared"
    assert prepared["parent_id"] == source_asset["id"]
    assert prepared["data_format"] == "markdown"
    assert prepared["preparation_params_json"]["method"] == "pymupdf_text"
    assert prepared["current_manifest_json"]["files"][0]["original_name"] == "policy.md"

    download_response = client.get(
        f"/v1/projects/{project_id}/data-assets/{prepared['id']}/files/download",
        params={"stored_path": "files/f_000001.md"},
    )
    assert download_response.status_code == 200
    assert "Payment is due within 30 days." in download_response.text


def test_prepare_source_asset_rejects_duplicate_running_job(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    project_id = _create_project(client)
    monkeypatch.setattr(
        "app.services.data_assets.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )
    upload_response = client.post(
        f"/v1/projects/{project_id}/data-assets/raw/upload",
        data={"name": "Policy text", "data_format": "text"},
        files={"files": ("policy.txt", b"Payment is due within 30 days.", "text/plain")},
    )
    assert upload_response.status_code == 201
    source_asset = upload_response.json()
    job_key = (project_id, source_asset["id"], "pymupdf_text")

    projects._claim_preparation_job(job_key)
    try:
        response = client.post(
            f"/v1/projects/{project_id}/data-assets/{source_asset['id']}/prepare",
            json={"method": "pymupdf_text", "settings": {"page_breaks": True}},
        )
    finally:
        projects._release_preparation_job(job_key)

    assert response.status_code == 409
    assert "already running" in response.json()["detail"]


def test_prepare_source_asset_with_docling_stores_markdown_and_json(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    project_id = _create_project(client)
    monkeypatch.setattr(
        "app.services.data_assets.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )

    def fake_prepare_docling(**kwargs):
        return [
            {
                "content": b"# Policy\n\nDocling markdown\n",
                "content_type": "text/markdown",
                "original_name": "policy.md",
                "role": "prepared_markdown",
                "source": {"original_name": "policy.pdf", "stored_path": "files/f_000001.pdf"},
            },
            {
                "content": b'{"schema_name":"DoclingDocument"}\n',
                "content_type": "application/json",
                "original_name": "policy.docling.json",
                "role": "docling_document_json",
                "source": {"original_name": "policy.pdf", "stored_path": "files/f_000001.pdf"},
            },
        ]

    monkeypatch.setattr("app.api.projects.prepare_docling", fake_prepare_docling)
    upload_response = client.post(
        f"/v1/projects/{project_id}/data-assets/raw/upload",
        data={"name": "Policy PDF", "data_format": "pdf"},
        files={"files": ("policy.pdf", b"%PDF synthetic", "application/pdf")},
    )
    assert upload_response.status_code == 201
    source_asset = upload_response.json()

    prepare_response = client.post(
        f"/v1/projects/{project_id}/data-assets/{source_asset['id']}/prepare",
        json={
            "method": "docling",
            "settings": {
                "base_url": "http://docling.local:5001",
                "do_ocr": True,
                "force_ocr": False,
                "image_export_mode": "placeholder",
            },
        },
    )

    assert prepare_response.status_code == 201
    prepared = prepare_response.json()
    assert prepared["asset_type"] == "prepared"
    assert prepared["parent_id"] == source_asset["id"]
    assert prepared["data_format"] == "mixed"
    assert prepared["preparation_params_json"]["method"] == "docling"
    assert prepared["preparation_params_json"]["output_formats"] == ["markdown", "json"]
    assert prepared["preparation_params_json"]["settings"] == {
        "do_ocr": True,
        "force_ocr": False,
        "image_export_mode": "placeholder",
    }
    assert prepared["preparation_params_json"]["service"] == {"base_url": "http://docling.local:5001"}
    files = prepared["current_manifest_json"]["files"]
    assert [file["original_name"] for file in files] == ["policy.md", "policy.docling.json"]
    assert [file["role"] for file in files] == ["prepared_markdown", "docling_document_json"]


def test_prepare_docling_uses_async_endpoint(monkeypatch, tmp_path) -> None:
    source_dir = tmp_path / "source"
    files_dir = source_dir / "files"
    files_dir.mkdir(parents=True)
    (files_dir / "f_000001.pdf").write_bytes(b"synthetic pdf")

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def json(self) -> dict:
            return self._payload

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.posts: list[str] = []
            self.gets: list[str] = []

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def post(self, url: str, json: dict):
            self.posts.append(url)
            assert url == "http://docling.test/v1/convert/source/async"
            assert json["options"]["image_export_mode"] == "embedded"
            assert json["options"]["to_formats"] == ["md", "json"]
            return FakeResponse({"task_id": "task-1", "task_status": "pending"})

        def get(self, url: str):
            self.gets.append(url)
            if url.endswith("/status/poll/task-1"):
                return FakeResponse({"task_id": "task-1", "task_status": "success"})
            if url.endswith("/result/task-1"):
                return FakeResponse(
                    {
                        "document": {
                            "json_content": {"schema_name": "DoclingDocument"},
                            "md_content": "# Policy\n",
                        }
                    }
                )
            raise AssertionError(url)

    fake_client = FakeClient()
    monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: fake_client)
    monkeypatch.setattr(
        "app.services.preparation.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "docling_async_max_wait_seconds": 30,
                "docling_base_url": "http://docling.test",
                "docling_poll_interval_seconds": 0.2,
                "docling_timeout_seconds": 5,
            },
        )(),
    )

    prepared_files = prepare_docling(
        image_export_mode="embedded",
        source_storage_path=str(source_dir),
        source_manifest={
            "files": [
                {
                    "original_name": "policy.pdf",
                    "stored_path": "files/f_000001.pdf",
                }
            ]
        },
    )

    assert fake_client.posts == ["http://docling.test/v1/convert/source/async"]
    assert fake_client.gets == [
        "http://docling.test/v1/status/poll/task-1",
        "http://docling.test/v1/result/task-1",
    ]
    assert [item["original_name"] for item in prepared_files] == [
        "policy.md",
        "policy.docling.json",
    ]


def test_upload_prepared_data_asset_requires_provenance(client: TestClient, monkeypatch, tmp_path) -> None:
    project_id = _create_project(client)
    raw_asset_id = _create_data_asset(client, project_id)
    monkeypatch.setattr(
        "app.services.data_assets.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )

    response = client.post(
        f"/v1/projects/{project_id}/data-assets/prepared/upload",
        data={
            "name": "Prepared Markdown",
            "data_format": "markdown",
            "parent_id": raw_asset_id,
            "preparation_params_json": '{"method":"external_gpu","output_format":"markdown"}',
        },
        files={"files": ("policy.md", b"# Policy\n\nSynthetic markdown", "text/markdown")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["asset_type"] == "prepared"
    assert body["parent_id"] == raw_asset_id
    assert body["preparation_params_json"]["method"] == "external_gpu"
    assert body["current_manifest_json"]["parent_id"] == raw_asset_id
    assert body["current_manifest_json"]["preparation_params_json"]["method"] == "external_gpu"


def test_add_and_delete_data_asset_files_updates_manifest(client: TestClient, monkeypatch, tmp_path) -> None:
    project_id = _create_project(client)
    monkeypatch.setattr(
        "app.services.data_assets.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )
    upload_response = client.post(
        f"/v1/projects/{project_id}/data-assets/raw/upload",
        data={"name": "Raw PDF", "data_format": "pdf"},
        files={"files": ("policy.pdf", b"one", "application/pdf")},
    )
    assert upload_response.status_code == 201
    asset = upload_response.json()
    first_hash = asset["manifest_hash"]

    add_response = client.post(
        f"/v1/projects/{project_id}/data-assets/{asset['id']}/files",
        files={"files": ("policy-extra.pdf", b"two", "application/pdf")},
    )
    assert add_response.status_code == 200
    added = add_response.json()
    assert added["manifest_hash"] != first_hash
    assert [file["stored_path"] for file in added["current_manifest_json"]["files"]] == [
        "files/f_000001.pdf",
        "files/f_000002.pdf",
    ]

    delete_response = client.delete(
        f"/v1/projects/{project_id}/data-assets/{asset['id']}/files",
        params={"stored_path": "files/f_000001.pdf"},
    )
    assert delete_response.status_code == 200
    deleted = delete_response.json()["data_asset"]
    assert [file["stored_path"] for file in deleted["current_manifest_json"]["files"]] == [
        "files/f_000002.pdf"
    ]


def test_delete_last_prepared_file_removes_prepared_asset(client: TestClient, monkeypatch, tmp_path) -> None:
    project_id = _create_project(client)
    data_asset_id = _upload_prepared_data_asset(client, monkeypatch, tmp_path, project_id)

    delete_response = client.delete(
        f"/v1/projects/{project_id}/data-assets/{data_asset_id}/files",
        params={"stored_path": "files/f_000001.md"},
    )

    assert delete_response.status_code == 200
    body = delete_response.json()
    assert body["deleted_data_asset_id"] == data_asset_id
    assert body["data_asset"] is None

    list_response = client.get(f"/v1/projects/{project_id}/data-assets")
    assert list_response.status_code == 200
    assert data_asset_id not in [asset["id"] for asset in list_response.json()["data_assets"]]


def test_delete_source_asset_removes_linked_prepared_assets(client: TestClient, monkeypatch, tmp_path) -> None:
    project_id = _create_project(client)
    raw_asset_id = _create_data_asset(client, project_id)
    prepared_asset_id = _upload_prepared_data_asset_with_parent(
        client,
        monkeypatch,
        tmp_path,
        project_id,
        raw_asset_id,
    )

    delete_response = client.delete(f"/v1/projects/{project_id}/data-assets/{raw_asset_id}")

    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_data_asset_ids"] == [prepared_asset_id, raw_asset_id]

    list_response = client.get(f"/v1/projects/{project_id}/data-assets")
    assert list_response.status_code == 200
    remaining_ids = [asset["id"] for asset in list_response.json()["data_assets"]]
    assert raw_asset_id not in remaining_ids
    assert prepared_asset_id not in remaining_ids


def test_delete_experiment_data_asset_is_blocked(client: TestClient, monkeypatch, tmp_path) -> None:
    project_id = _create_project(client)
    data_asset_id = _upload_prepared_data_asset(client, monkeypatch, tmp_path, project_id)
    parameter_set_id = _create_parameter_set(client, project_id)
    response = client.post(
        f"/v1/projects/{project_id}/saved-experiments",
        json={
            "name": "Uses prepared data",
            "data_asset_id": data_asset_id,
            "parameter_set_id": parameter_set_id,
            "params_hash": "sha256:test-params",
            "params_snapshot_json": {"retrieval": {"mode": "dense"}},
        },
    )
    assert response.status_code == 201

    delete_response = client.delete(f"/v1/projects/{project_id}/data-assets/{data_asset_id}")

    assert delete_response.status_code == 400
    assert "saved experiments" in delete_response.json()["detail"]


def test_delete_experiment_parameter_set_is_blocked(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    project_id = _create_project(client)
    data_asset_id = _upload_prepared_data_asset(client, monkeypatch, tmp_path, project_id)
    parameter_set_id = _create_parameter_set(client, project_id)
    response = client.post(
        f"/v1/projects/{project_id}/saved-experiments",
        json={
            "name": "Uses parameter set",
            "data_asset_id": data_asset_id,
            "parameter_set_id": parameter_set_id,
            "params_hash": "sha256:test-params",
            "params_snapshot_json": {"retrieval": {"mode": "dense"}},
        },
    )
    assert response.status_code == 201

    delete_response = client.delete(f"/v1/projects/{project_id}/parameter-sets/{parameter_set_id}")

    assert delete_response.status_code == 400
    assert "saved experiments" in delete_response.json()["detail"]


def test_create_ground_truth_set_under_project(client: TestClient) -> None:
    project_id = _create_project(client)
    data_asset_id = _create_data_asset(client, project_id)

    response = client.post(
        f"/v1/projects/{project_id}/ground-truth-sets",
        json={
            "name": "Policy questions",
            "data_asset_id": data_asset_id,
            "storage_path": "data/ground_truth/policy_questions.jsonl",
            "manifest_hash": "sha256:test-ground-truth",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project_id
    assert body["data_asset_id"] == data_asset_id
    assert body["name"] == "Policy questions"

    list_response = client.get(f"/v1/projects/{project_id}/ground-truth-sets")
    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()["ground_truth_sets"]] == [
        "Policy questions"
    ]


def test_create_saved_experiment_with_metrics_json(client: TestClient, monkeypatch, tmp_path) -> None:
    project_id = _create_project(client)
    data_asset_id = _upload_prepared_data_asset(client, monkeypatch, tmp_path, project_id)
    parameter_set_id = _create_parameter_set(client, project_id)

    response = client.post(
        f"/v1/projects/{project_id}/saved-experiments",
        json={
            "name": "Hybrid baseline",
            "data_asset_id": data_asset_id,
            "parameter_set_id": parameter_set_id,
            "params_hash": "sha256:test-params",
            "params_snapshot_json": {
                "preparation": {"converter": "pymupdf_text"},
                "chunking": {"chunk_size": 900},
                "retrieval": {"mode": "hybrid", "top_k": 8},
            },
            "metrics_summary_json": {
                "hit_at_5": 0.8,
                "mrr": 0.7,
                "latency_ms": 250,
            },
            "debug_level": "none",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project_id
    assert body["metrics_summary_json"] == {
        "hit_at_5": 0.8,
        "mrr": 0.7,
        "latency_ms": 250,
    }
    assert body["data_asset_manifest_hash"].startswith("sha256:")


def _create_project(client: TestClient) -> str:
    response = client.post("/v1/projects", json={"name": "Policy RAG"})
    assert response.status_code == 201
    return response.json()["id"]


class FakeEmbedder:
    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [[float(index + 1), float(len(text))] for index, text in enumerate(texts)]

    def embed_query(self, query: str) -> list[float]:
        return [1.0, float(len(query))]


class FakeQdrantStore:
    def __init__(self) -> None:
        self.collection_name = ""
        self.points: list[dict] = []

    def ensure_collection(
        self,
        *,
        collection_name: str,
        vector_size: int,
        distance: str,
        sparse: bool = False,
    ) -> None:
        self.collection_name = collection_name
        assert vector_size == 384
        assert distance == "Cosine"
        assert sparse is True

    def upsert_points(self, *, collection_name: str, points: list[dict]) -> None:
        assert collection_name == self.collection_name
        self.points = points

    def search_dense(self, *, collection_name: str, query_vector: list[float], top_k: int) -> list[dict]:
        assert collection_name == self.collection_name
        assert query_vector
        return [
            {
                "payload": self.points[0]["payload"],
                "score": 0.99,
            }
        ][:top_k]

    def search_sparse(self, *, collection_name: str, query_vector: dict, top_k: int) -> list[dict]:
        assert collection_name == self.collection_name
        assert query_vector["indices"]
        return [
            {
                "payload": self.points[0]["payload"],
                "score": 0.88,
            }
        ][:top_k]


class FailingQdrantStore(FakeQdrantStore):
    def ensure_collection(
        self,
        *,
        collection_name: str,
        vector_size: int,
        distance: str,
        sparse: bool = False,
    ) -> None:
        raise RuntimeError("Qdrant is unavailable")


def fake_create_embedder(model_id: str, params: dict | None = None) -> FakeEmbedder:
    assert model_id == "intfloat_multilingual_e5_small"
    assert params is not None
    return FakeEmbedder()


def _patch_data_dirs(monkeypatch, tmp_path) -> None:
    settings = type(
        "Settings",
        (),
        {
            "data_dir": tmp_path,
            "qdrant_url": "http://localhost:6333",
        },
    )()
    monkeypatch.setattr("app.services.data_assets.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.runtime_cache.get_settings", lambda: settings)


def _make_text_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    payload = doc.tobytes()
    doc.close()
    return payload


def _create_data_asset(client: TestClient, project_id: str) -> str:
    response = client.post(
        f"/v1/projects/{project_id}/data-assets",
        json={
            "name": "Prepared policies",
            "asset_type": "raw",
            "data_format": "pdf",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_prepared_data_asset(client: TestClient, project_id: str) -> str:
    raw_asset_id = _create_data_asset(client, project_id)
    response = client.post(
        f"/v1/projects/{project_id}/data-assets",
        json={
            "name": "Prepared policies",
            "asset_type": "prepared",
            "data_format": "markdown",
            "parent_id": raw_asset_id,
            "preparation_params_json": {
                "method": "external_gpu",
                "tool": "marker",
                "output_format": "markdown",
            },
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _upload_prepared_data_asset(
    client: TestClient,
    monkeypatch,
    tmp_path,
    project_id: str,
) -> str:
    raw_asset_id = _create_data_asset(client, project_id)
    monkeypatch.setattr(
        "app.services.data_assets.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )
    response = client.post(
        f"/v1/projects/{project_id}/data-assets/prepared/upload",
        data={
            "name": "Prepared policies",
            "data_format": "markdown",
            "parent_id": raw_asset_id,
            "preparation_params_json": '{"method":"external_gpu","output_format":"markdown"}',
        },
        files={"files": ("policy.md", b"# Policy", "text/markdown")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _upload_prepared_data_asset_with_parent(
    client: TestClient,
    monkeypatch,
    tmp_path,
    project_id: str,
    raw_asset_id: str,
) -> str:
    monkeypatch.setattr(
        "app.services.data_assets.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )
    response = client.post(
        f"/v1/projects/{project_id}/data-assets/prepared/upload",
        data={
            "name": "Prepared policies",
            "data_format": "markdown",
            "parent_id": raw_asset_id,
            "preparation_params_json": '{"method":"external_gpu","output_format":"markdown"}',
        },
        files={"files": ("policy.md", b"# Policy", "text/markdown")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _upload_prepared_data_asset_with_content(
    client: TestClient,
    monkeypatch,
    tmp_path,
    project_id: str,
    content: bytes,
) -> str:
    raw_asset_id = _create_data_asset(client, project_id)
    monkeypatch.setattr(
        "app.services.data_assets.get_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )
    response = client.post(
        f"/v1/projects/{project_id}/data-assets/prepared/upload",
        data={
            "name": "Prepared policies",
            "data_format": "markdown",
            "parent_id": raw_asset_id,
            "preparation_params_json": '{"method":"external_gpu","output_format":"markdown"}',
        },
        files={"files": ("policy.md", content, "text/markdown")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_parameter_set(client: TestClient, project_id: str) -> str:
    response = client.post(
        f"/v1/projects/{project_id}/parameter-sets",
        json={
            "name": "Baseline",
            "params_hash": "sha256:test-params",
            "params_json": {"retrieval": {"mode": "dense", "top_k": 5}},
        },
    )
    assert response.status_code == 201
    return response.json()["id"]
