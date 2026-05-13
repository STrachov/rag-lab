from fastapi.testclient import TestClient
import fitz


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
    assert body["params_json"]["preparation"]["converter"] == "docling"


def test_list_chunking_strategies_for_parameters_ui(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.get(f"/v1/projects/{project_id}/parameter-sets/chunking/strategies")

    assert response.status_code == 200
    strategies = response.json()["strategies"]
    strategy_ids = [strategy["id"] for strategy in strategies]
    assert "heading_recursive" in strategy_ids
    assert "recursive" in strategy_ids
    assert "langchain_recursive_character" in strategy_ids
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
        json={"method": "pymupdf_text", "output_format": "markdown", "page_breaks": True},
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
