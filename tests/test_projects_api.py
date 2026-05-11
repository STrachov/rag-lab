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


def test_create_saved_experiment_with_metrics_json(client: TestClient) -> None:
    project_id = _create_project(client)
    data_asset_id = _create_data_asset(client, project_id)
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
        json={"name": "Prepared policies", "asset_type": "prepared"},
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
