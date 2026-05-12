from fastapi.testclient import TestClient


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
    assert body["metadata_json"]["file_count"] == 1


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


def test_create_saved_experiment_with_metrics_json(client: TestClient) -> None:
    project_id = _create_project(client)
    data_asset_id = _create_prepared_data_asset(client, project_id)
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


def _create_project(client: TestClient) -> str:
    response = client.post("/v1/projects", json={"name": "Policy RAG"})
    assert response.status_code == 201
    return response.json()["id"]


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
