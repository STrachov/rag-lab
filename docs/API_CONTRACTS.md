# API Contracts

## Purpose

Planned API surface for RAG Lab.

## Error Shape

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

## Projects

```http
GET  /v1/projects
POST /v1/projects
GET  /v1/projects/{project_id}
```

## Data Assets

```http
GET  /v1/projects/{project_id}/data-assets
POST /v1/projects/{project_id}/data-assets
POST /v1/projects/{project_id}/data-assets/raw/upload
POST /v1/projects/{project_id}/data-assets/prepared/upload
POST /v1/projects/{project_id}/data-assets/{data_asset_id}/files
DELETE /v1/projects/{project_id}/data-assets/{data_asset_id}/files?stored_path=...
DELETE /v1/projects/{project_id}/data-assets/{data_asset_id}
GET  /v1/projects/{project_id}/data-assets/{data_asset_id}/files/download?stored_path=...
POST /v1/projects/{project_id}/data-assets/{data_asset_id}/prepare
```

Upload endpoints store files under project-scoped storage using generated safe filenames. Original filenames are recorded in manifest JSON.

PDF uploads are inspected with a lightweight CPU pass. Manifest entries may include page count, encryption status, text-layer metrics, image counts, scan likelihood, and document metadata. Inspection failures are recorded in the manifest and should not fail the upload.

Adding or deleting files creates a new manifest snapshot in `data_asset_manifests` and updates `data_assets.manifest_hash`.

Deleting an individual file preserves prior manifest snapshots for that asset. Deleting a whole source data asset deletes its linked prepared versions as well. Deleting any data asset used by saved experiments is blocked.

Prepared data uploads must include preparation provenance metadata. Saved experiments should reference prepared data assets, not raw data assets, and snapshot `data_asset_manifest_hash`.

The initial local preparation method is `pymupdf_text`, which converts PDFs with extractable text layers plus `.txt` and `.md` files into prepared Markdown.

## Parameter Sets

```http
GET  /v1/projects/{project_id}/parameter-sets
POST /v1/projects/{project_id}/parameter-sets
GET  /v1/projects/{project_id}/parameter-sets/chunking/strategies
POST /v1/projects/{project_id}/parameter-sets/chunking/preview
```

`chunking/strategies` is the backend-owned catalog for available chunking methods. Each strategy
declares its id, label, description, default parameters, and UI fields. Adding a strategy in code and
registering it in the chunking registry should make it available to the Parameters UI without a
frontend code change.

Strategies may be native or adapter-backed. For example, `langchain_recursive_character` uses
LangChain's `RecursiveCharacterTextSplitter` through the chunking adapter boundary while still
returning RAG Lab chunk preview records.

`chunking/preview` accepts a prepared `data_asset_id` plus chunking parameters and returns
summary statistics, warnings, and preview chunks. It does not create a product result or saved
experiment. Preview chunks are derived runtime/debug output and may be recomputed from the prepared
data asset manifest plus chunking parameters.

Canonical chunking payload:

```json
{
  "strategy": "heading_recursive",
  "params": {
    "chunk_size": 900,
    "chunk_overlap": 120
  }
}
```

## Ground Truth Sets

```http
GET  /v1/projects/{project_id}/ground-truth-sets
POST /v1/projects/{project_id}/ground-truth-sets
```

## Saved Experiments

```http
GET  /v1/projects/{project_id}/saved-experiments
POST /v1/projects/{project_id}/saved-experiments
```

Saved experiment creation snapshots the current `data_assets.manifest_hash` into `data_asset_manifest_hash`.

## Metrics

Saved experiment results are metrics only. Metrics may be returned in:

```text
metrics_summary_json
MetricValue rows
```

## Derived Cache

Chunks, embeddings, Qdrant indexes, traces, prompts, and generated answers are not core API results. Future debug endpoints should make the cache/debug status explicit.

## Breaking-Change Rule

After implementation, treat endpoint renames, required-field changes, response-shape changes, and error-shape changes as breaking.
