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
GET  /v1/projects/{project_id}/data-assets/preparation/methods
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

Preparation methods are backend-driven and exposed through `preparation/methods`. The first methods are:

```text
pymupdf_text -> Markdown from PDFs with text layers, text files, and Markdown files
docling -> Markdown plus Docling JSON through an external Docling Serve endpoint
```

Docling output stores `*.md` and `*.docling.json` files in the prepared data asset manifest. No separate RAG Lab metadata JSON is created at preparation time.

Docling preparation uses the async Docling Serve flow internally: submit to `/v1/convert/source/async`, poll `/v1/status/poll/{task_id}`, then read `/v1/result/{task_id}`. This avoids the server-side timeout of synchronous conversion for slow CPU/OCR jobs.

Preparation requests use method-specific settings rather than fixed top-level fields:

```json
{
  "name": "Policy docling",
  "method": "docling",
  "settings": {
    "base_url": "http://localhost:5001",
    "do_ocr": true,
    "force_ocr": false,
    "image_export_mode": "placeholder"
  }
}
```

RAG Lab exposes Docling image export modes `placeholder` and `embedded`. Docling also supports `referenced`, but RAG Lab does not expose it yet because referenced image files must be captured and stored as prepared asset files.

## Parameter Sets

```http
GET  /v1/projects/{project_id}/parameter-sets
POST /v1/projects/{project_id}/parameter-sets
DELETE /v1/projects/{project_id}/parameter-sets/{parameter_set_id}
GET  /v1/projects/{project_id}/parameter-sets/chunking/strategies
POST /v1/projects/{project_id}/parameter-sets/chunking/preview
```

Parameter sets include a `category` field such as `chunking`, `embedding`, `retrieval`,
`generation`, `evaluation`, or `general`. Deleting a parameter set used by a saved experiment is
blocked.

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
