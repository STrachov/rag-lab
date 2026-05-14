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

Parameter sets include a `category` field such as `chunking`, `embedding`, `indexing`,
`retrieval`, `generation`, `evaluation`, or `general`. Deleting a parameter set used by a saved
experiment is blocked.

`chunking/strategies` is the backend-owned catalog for available chunking methods. Each strategy
declares its id, label, description, default parameters, and UI fields. Adding a strategy in code and
registering it in the chunking registry should make it available to the Chunking UI without a
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

## Runtime Caches, Indexing, And Retrieval

```http
GET  /v1/projects/{project_id}/derived-cache?cache_type=...
GET  /v1/projects/{project_id}/embedding/models
GET  /v1/projects/{project_id}/sparse/models
GET  /v1/projects/{project_id}/reranking/models
POST /v1/projects/{project_id}/chunks/materialize
GET  /v1/projects/{project_id}/chunks/{chunks_cache_id}/gt-authoring-pack
POST /v1/projects/{project_id}/indexes/qdrant
POST /v1/projects/{project_id}/retrieve/preview
POST /v1/projects/{project_id}/rerank/preview
```

`derived-cache` returns project-scoped `DerivedCache` entries. The Retrieval UI uses it to restore
existing Qdrant index caches after navigation and to show failed index attempts.

`embedding/models` and `sparse/models` are backend-owned catalogs. The first embedding models are
local SentenceTransformers models:

```text
intfloat_multilingual_e5_small -> intfloat/multilingual-e5-small
baai_bge_small_en_v1_5 -> BAAI/bge-small-en-v1.5
```

The first sparse model is `bm25_local`. Its user-tunable params include `k1` and `b` as floats:

```text
k1: 0.0..4.0, default 1.2, step 0.05
b:  0.0..1.0, default 0.75, step 0.05
```

The first reranker models are local cross-encoders exposed through a backend-owned catalog:

```text
baai_bge_reranker_v2_m3 -> BAAI/bge-reranker-v2-m3
qwen3_reranker_0_6b -> Qwen/Qwen3-Reranker-0.6B
ms_marco_minilm_l6_v2 -> cross-encoder/ms-marco-MiniLM-L6-v2
```

`chunks/materialize` accepts a prepared `data_asset_id` plus a canonical chunking snapshot and writes
normalized chunk JSONL under `data/cache/chunks/{cache_key}/`. It creates or reuses
`DerivedCache(cache_type="chunks")`. Docling JSON files are recorded as sidecar metadata, not indexed
as chunk text by default.

`gt-authoring-pack` downloads a zip for offline/manual or ChatGPT-assisted ground truth authoring.
The pack includes:

```text
manifest.json
chunks.jsonl
chunks_manifest.json
prepared_text/
ground_truth.schema.json
ground_truth.template.jsonl
instructions.md
```

This endpoint requires a materialized chunks cache. It is a debug/export affordance, not a saved
experiment result.

Qdrant index creation accepts a chunks cache plus indexing options:

```json
{
  "chunks_cache_id": "uuid",
  "index_mode": "hybrid",
  "collection_name": "optional_collection_name",
  "embedding": {
    "model_id": "intfloat_multilingual_e5_small",
    "params": {
      "device": "cpu"
    }
  },
  "sparse": {
    "model_id": "bm25_local",
    "params": {
      "lowercase": true,
      "min_token_len": 2,
      "k1": 1.2,
      "b": 0.75
    }
  },
  "distance": "Cosine"
}
```

Current Qdrant collections use named vectors: `dense` for dense embeddings and `sparse` for BM25-style
sparse vectors. `index_mode` may be `dense`, `sparse`, or `hybrid`. Failed Qdrant indexing should
return an HTTP error and also create `DerivedCache(status="failed")` with `metadata_json.error_json`.

Retrieval preview accepts a Qdrant index cache, query, mode, and `top_k`:

```json
{
  "index_cache_id": "uuid",
  "query": "What is the policy?",
  "mode": "hybrid",
  "top_k": 5,
  "candidate_k": 30
}
```

Response rows include source metadata, `score`, optional `dense_score`, optional `sparse_score`, and a
clipped `text_preview`. Hybrid preview currently merges dense and sparse Qdrant searches in the
application layer with reciprocal rank fusion. The response includes `retrieval_cache_id`; the
backend stores the full candidate set in `DerivedCache(cache_type="retrieval_temp")` so reranking can
be repeated without another Qdrant search.

Rerank preview accepts a retrieval cache and reranker settings:

```json
{
  "retrieval_cache_id": "uuid",
  "top_k": 5,
  "reranking": {
    "enabled": true,
    "model_id": "qwen3_reranker_0_6b",
    "params": {
      "device": "cpu",
      "batch_size": 8,
      "max_length": 512,
      "normalize_scores": true
    }
  }
}
```

Reranking loads the saved candidate set from `retrieval_temp`, loads full chunk text from the
materialized chunks cache, scores query/chunk pairs with the selected reranker, and returns the final
`top_k`. Result rows include `rerank_score`, `original_score`, and `original_rank`. Full chunk text is
not stored in Qdrant payloads or retrieval temp metadata.

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

Chunks, embeddings, sparse statistics, Qdrant indexes, traces, prompts, and generated answers are not
core API results. Debug/runtime endpoints must keep the cache/debug status explicit and must not turn
retrieval previews into saved experiment metrics.

## Breaking-Change Rule

After implementation, treat endpoint renames, required-field changes, response-shape changes, and error-shape changes as breaking.
