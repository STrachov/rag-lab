# API Contracts

## Purpose

This document defines the UI/backend boundary for RAG Lab. Product intent lives in
`PRODUCT_SPEC.md`; domain entities live in `DOMAIN_MODEL.md`.

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

## Data Assets And Preparation

```http
GET    /v1/projects/{project_id}/data-assets
POST   /v1/projects/{project_id}/data-assets
POST   /v1/projects/{project_id}/data-assets/raw/upload
POST   /v1/projects/{project_id}/data-assets/prepared/upload
POST   /v1/projects/{project_id}/data-assets/{data_asset_id}/files
DELETE /v1/projects/{project_id}/data-assets/{data_asset_id}/files?stored_path=...
DELETE /v1/projects/{project_id}/data-assets/{data_asset_id}
GET    /v1/projects/{project_id}/data-assets/{data_asset_id}/files/download?stored_path=...
GET    /v1/projects/{project_id}/data-assets/preparation/methods
POST   /v1/projects/{project_id}/data-assets/{data_asset_id}/prepare
```

Uploads store files under generated safe filenames and keep original filenames in manifest JSON.
PDF uploads should record lightweight inspection hints such as page count, encryption status,
text-layer signal, image counts, scan likelihood, and inspection failure details.

Preparation methods are backend-driven registry entries. The UI must render the method selector and
method-specific controls from the registry response.

Preparation request:

```json
{
  "name": "Policy docling",
  "method_id": "docling",
  "params": {
    "do_ocr": true,
    "force_ocr": false,
    "image_export_mode": "placeholder"
  }
}
```

The first methods are:

```text
pymupdf_text
docling
```

Docling uses the async Docling Serve flow internally and stores Markdown plus `*.docling.json`.
Expose `image_export_mode` values `placeholder` and `embedded`; do not expose `referenced` until
referenced image files are stored as prepared asset files.

## Stage Catalogs And Parameter Sets

```http
GET    /v1/projects/{project_id}/parameter-sets
POST   /v1/projects/{project_id}/parameter-sets
DELETE /v1/projects/{project_id}/parameter-sets/{parameter_set_id}

GET    /v1/projects/{project_id}/parameter-sets/chunking/strategies
POST   /v1/projects/{project_id}/parameter-sets/chunking/preview

GET    /v1/projects/{project_id}/embedding/models
GET    /v1/projects/{project_id}/sparse/models
GET    /v1/projects/{project_id}/reranking/models
```

Generation model/prompt catalogs and evaluation-metric catalogs are planned, but are not part of the
current implemented API contract.

Parameter sets include a `category` such as:

```text
preparation
chunking
embedding
indexing
retrieval
reranking
generation
evaluation
general
```

Deleting a parameter set used by a saved experiment is blocked. Preparation ParameterSets are
reusable presets; prepared data assets store the applied preparation snapshot in
`preparation_params_json`.

Chunking preview payload:

```json
{
  "data_asset_id": "uuid",
  "chunking": {
    "strategy": "heading_recursive",
    "params": {
      "chunk_size": 900,
      "chunk_overlap": 120
    }
  }
}
```

Preview responses return summary statistics, warnings, and preview chunks. They do not create saved
experiment results. The `max_chunks` request field limits how many chunks are returned in the UI
preview. The returned `text_preview` field contains the full text of each returned chunk; it is named
`text_preview` for API compatibility, not because it is clipped.

## Runtime Caches, Indexing, Retrieval, Reranking

```http
GET  /v1/projects/{project_id}/derived-cache?cache_type=...
POST /v1/projects/{project_id}/chunks/materialize
GET  /v1/projects/{project_id}/chunks/{chunks_cache_id}/gt-authoring-pack
POST /v1/projects/{project_id}/indexes/qdrant
POST /v1/projects/{project_id}/retrieve/preview
POST /v1/projects/{project_id}/rerank/preview
```

`chunks/materialize` accepts a prepared data asset and canonical chunking snapshot, writes
`raglab.chunks.v1` JSONL, and creates or reuses `DerivedCache(cache_type="chunks")`.

Qdrant index request:

```json
{
  "chunks_cache_id": "uuid",
  "index_mode": "hybrid",
  "collection_name": "",
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

Current Qdrant collections use named vectors: `dense` and optional `sparse`. Dense embedding models
may be local or remote catalog entries. Remote Voyage entries include `voyage_4_lite` and
`voyage_4_large`; their `output_dimension` parameter controls the Qdrant dense vector size and is
stored in the embedding snapshot. Failed index attempts should return an HTTP error and also create
`DerivedCache(status="failed")` with `metadata_json.error_json`.

Retrieval preview request:

```json
{
  "index_cache_id": "uuid",
  "query": "What is the policy?",
  "mode": "hybrid",
  "strategy": "parent_page_retrieval",
  "parent_score": "max",
  "top_k": 5,
  "candidate_k": 30
}
```

Retrieval preview returns source metadata, scores, clipped `text_preview`, and a
`retrieval_cache_id`. `strategy` may be `chunk_retrieval`, `parent_page_retrieval`, or
`parent_chapter_retrieval`. Parent retrieval strategies group retrieved child chunks by parent id and
return parent page/chapter contexts. Reranking reads the saved candidate set from `retrieval_temp` so
users can sweep reranker params without repeating Qdrant retrieval.

Rerank preview request:

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

Reranker catalog entries may be local `sentence_transformers` cross-encoders, remote Voyage API
entries, or an OpenAI LLM-as-reranker entry. Voyage entries are `voyage_rerank_2_5` and
`voyage_rerank_2_5_lite`; when selected, rerank preview sends the query and full text for the current
retrieval candidate cache to Voyage `/v1/rerank` and stores only scores plus the existing retrieval
metadata in the preview response. `openai_llm_reranker` sends query plus candidate text batches to
OpenAI Chat Completions, requests strict JSON relevance scores, stores `llm_score` and normalized
retrieval score metadata, and uses `llm_weight` / `retrieval_weight` to compute final rerank scores.

## Ground Truth Sets

```http
GET    /v1/projects/{project_id}/ground-truth-sets
POST   /v1/projects/{project_id}/ground-truth-sets/upload
GET    /v1/projects/{project_id}/ground-truth-sets/{ground_truth_set_id}/files/{canonical|original}
GET    /v1/projects/{project_id}/ground-truth-sets/{ground_truth_set_id}/questions
POST   /v1/projects/{project_id}/ground-truth-sets/{ground_truth_set_id}/score-ranking
DELETE /v1/projects/{project_id}/ground-truth-sets/{ground_truth_set_id}
```

Ground truth upload accepts JSON or JSONL plus an optional prepared `data_asset_id`. Upload validates
shape and canonicalizes the file. Chunk-id compatibility is checked later against the selected
chunks cache during retrieval/reranking evaluation.

Ground truth question list responses include optional `expected_answer` and
`expected_answer_brief` fields when the uploaded ground truth provides an answer value. These fields
are omitted for question records that only define relevance judgments.

`score-ranking` evaluates one ranked preview result for one ground-truth question and returns metrics
only. Batch evaluation should reuse the same scorer family.

## Saved Experiments And Evaluation

```http
GET  /v1/projects/{project_id}/saved-experiments
POST /v1/projects/{project_id}/saved-experiments
GET  /v1/projects/{project_id}/saved-experiments/{saved_experiment_id}
PATCH /v1/projects/{project_id}/saved-experiments/{saved_experiment_id}
DELETE /v1/projects/{project_id}/saved-experiments/{saved_experiment_id}
POST /v1/projects/{project_id}/saved-experiments/{saved_experiment_id}/evaluate
```

Saved experiment creation snapshots the current prepared data asset manifest hash and stores the
full parameter snapshot. The current evaluation endpoint runs synchronously; background execution
should be added later when evaluations may call slow models, build caches, or score large
ground-truth sets.

Create saved experiment request:

```json
{
  "name": "Hybrid e5 bm25 qwen strict",
  "data_asset_id": "prepared-data-uuid",
  "ground_truth_set_id": "ground-truth-uuid",
  "params_snapshot_json": {},
  "debug_level": "none",
  "notes": ""
}
```

Evaluate response:

```json
{
  "id": "uuid",
  "project_id": "uuid",
  "name": "Hybrid e5 bm25 qwen strict",
  "status": "completed",
  "metrics_summary_json": {
    "evaluation": {},
    "metric_averages": {},
    "questions": []
  }
}
```

Evaluation request body is optional. If supplied, `index_cache_id` overrides the index cache stored
in `params_snapshot_json`:

```json
{
  "index_cache_id": "uuid"
}
```

Metrics are currently returned in:

```text
SavedExperiment.metrics_summary_json
```

`MetricValue` remains part of the domain model for future normalized metric storage, but current GT
evaluation does not populate separate metric rows.

The current implementation of `POST /v1/projects/{project_id}/saved-experiments/{saved_experiment_id}/evaluate`
runs synchronously. It reads `index_cache_id`, retrieval params, and optional enabled reranking params
from `SavedExperiment.params_snapshot_json`, loops over every question in the linked ground truth set,
retrieves/reranks candidates, scores them with the existing single-question scorer, and stores:

```text
metrics_summary_json.evaluation
metrics_summary_json.metric_averages
metrics_summary_json.questions
```

Per-question rows store metrics, warnings, error metadata, `ground_truth` expectations, and compact
`retrieved` top-k metadata. Retrieved metadata may include ids, source names, page numbers, ranks,
and scores, but must not store full chunk text unless a later explicit debug-full mode is added.
The scorer can emit chunk-level metrics such as `hit_at_k`, `mrr_at_k`, and `recall_at_k`, and
page-oriented metrics such as `page_hit_at_k`, `page_mrr_at_k`, and `page_recall_at_k`. The Saved
Experiments list displays compact aggregate values and falls back from chunk-level keys to page-level
keys when needed. The saved experiment detail page is the canonical result view. Retrieval preview may
launch evaluation and link to the saved result, but should not duplicate the full per-question result
table inline.

## Breaking-Change Rule

After implementation, endpoint renames, required-field changes, response-shape changes, and
error-shape changes are breaking changes.
