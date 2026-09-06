# API Contracts

## Purpose

This document defines the UI/backend boundary for RAG Lab. Product intent lives in
`PRODUCT_SPEC.md`; domain entities live in `DOMAIN_MODEL.md`.

## Error Shape

The API currently uses FastAPI's standard error envelopes. Application errors usually return:

```json
{
  "detail": "message"
}
```

Request-validation errors return `detail` as an array of validation records. A custom
`error.code/message/details` envelope is not implemented and must not be assumed by clients.

## Health And Reserved Stubs

```http
GET  /v1/health
POST /v1/ask
POST /v1/retrieve
POST /v1/experiments
```

Only `GET /v1/health` is implemented. The three generic POST endpoints are reserved stubs that return
HTTP 501. Use the project-scoped retrieval-preview and saved-experiment endpoints documented below.

## Projects

```http
GET   /v1/projects
POST  /v1/projects
GET   /v1/projects/{project_id}
PATCH /v1/projects/{project_id}
```

Projects use the user-facing lifecycle statuses `active` and `archived`. `GET /v1/projects`
returns all projects by default and accepts `?status=active` or `?status=archived`. PATCH partially
updates `name`, `description`, `domain`, `status`, or `metadata_json`; an empty project name is
rejected. Archiving is organizational and does not delete data or prevent the project from being
opened.

## Data Assets And Preparation

```http
GET    /v1/projects/{project_id}/data-assets
POST   /v1/projects/{project_id}/data-assets
POST   /v1/projects/{project_id}/data-assets/raw/upload
POST   /v1/projects/{project_id}/data-assets/prepared/upload
POST   /v1/projects/{project_id}/data-assets/{data_asset_id}/files
DELETE /v1/projects/{project_id}/data-assets/{data_asset_id}/files?stored_path=...
DELETE /v1/projects/{project_id}/data-assets/{data_asset_id}?cascade_derived_cache=false
GET    /v1/projects/{project_id}/data-assets/{data_asset_id}/files/download?stored_path=...
GET    /v1/projects/{project_id}/data-assets/preparation/methods
POST   /v1/projects/{project_id}/data-assets/{data_asset_id}/prepare
```

Deleting a data asset is blocked while saved experiments reference it. It is also blocked while
derived caches reference it unless `cascade_derived_cache=true`; cascading deletes dependent runtime
caches/storage before deleting the asset. Deleting a source asset also includes its linked prepared
assets.

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

`POST /parameter-sets` currently requires the client to submit `params_hash` together with
`params_json`; the backend does not derive that hash automatically.

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
DELETE /v1/projects/{project_id}/derived-cache/{cache_id}?cascade_dependents=false
POST /v1/projects/{project_id}/chunks/materialize
GET  /v1/projects/{project_id}/chunks/{chunks_cache_id}/gt-authoring-pack
POST /v1/projects/{project_id}/indexes/qdrant
POST /v1/projects/{project_id}/retrieve/preview
POST /v1/projects/{project_id}/rerank/preview
```

Deleting a cache with dependent runtime caches returns HTTP 409 unless
`cascade_dependents=true`. Current creation paths use `chunks`, `qdrant_index`, and
`retrieval_temp`; `embeddings` and `answer_temp` are reserved schema values.

`chunks/materialize` accepts a prepared data asset and canonical chunking snapshot, writes
`raglab.chunks.v1` JSONL to a fresh materialization location, and creates `DerivedCache(cache_type="chunks")`
with exact `chunks_file_sha256`, chunk count and effective size unit. Each index build gets a distinct
physical collection based on its cache ID and stores verified `input_chunks_sha256` plus sparse statistics
hash when applicable. Requested collection names do not select shared physical collections.

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
The OpenAI model parameter is a backend-catalog `select` field; its default and option list come from
backend settings so deployments can update available model names without frontend changes.
Remote reranking responses may include a `usage.reranking` object with provider/model, request and
retry counts, candidate count, token counts, `duration_seconds`, and `estimated_cost_usd`. OpenAI
usage uses provider-reported token counts; Voyage
rerank usage uses the local token estimate used for rate-limit planning. API reranker price fields
are returned in the reranker catalog and are also saved in reranking params, so saved experiments keep
the price assumptions used when they were run.

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
shape, canonicalizes the file and records exact canonical UTF-8 byte SHA-256 as `canonical_sha256` in
manifest/metadata. Readers verify this hash; GT without it must be re-imported. Chunk-id compatibility is checked later against the selected
chunks cache during retrieval/reranking evaluation.

`raglab.ground_truth.v1` remains backward compatible. A question may include optional metadata, and
the canonical object may declare optional evaluation slices:

```json
{
  "schema_version": "raglab.ground_truth.v1",
  "evaluation_slices": [
    {
      "id": "hard",
      "label": "Hard",
      "filter": {"difficulty": ["hard"]}
    }
  ],
  "questions": [
    {
      "question_id": "q001",
      "question": "...",
      "metadata": {
        "source": "benchmark_original",
        "difficulty": "hard",
        "tags": ["numeric", "multi_page"]
      }
    }
  ]
}
```

`source` and `difficulty` accept a string or null; `tags` accepts an array of strings. Values are
benchmark-defined, not backend enums. Slice filter values are string arrays. Different keys are
ANDed, values within a key are ORed, and `tags` matches when any question tag is allowed.
Duplicate allowed values are removed in first-occurrence order. Empty filters and empty allowed-value
arrays are rejected.

Qrels `relevant_pages` and `relevant_chunks`, when supplied, must be arrays of valid judgment objects;
null, other collection types, and malformed entries are rejected, never silently discarded. Omitted
collections default to empty arrays. Found page-level questions require pages and cannot include
chunk judgments; found chunk-level questions require chunks and cannot include page judgments.
Not-found questions cannot include relevance judgments. Authoring `expected_chunks` and raw page
`references` collections use the same strict array/object checks.

Authoring records use `metadata.difficulty`. Legacy top-level `difficulty` remains accepted and is
imported into that same metadata field. If both fields are supplied, they must agree (including null)
or upload is rejected. New authoring templates expose only `metadata.difficulty`; the legacy schema
property is marked deprecated. Other question metadata is preserved.

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

SavedExperiment is one backend-generated immutable pipeline snapshot and one evaluation attempt.
The backend resolves historical source/prepared manifests through the selected ready Qdrant index
and chunks cache. Creation rejects unverified inputs; old development records/caches/GT must be recreated.
See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for the complete snapshot and hash contract.

Create request:

```json
{
  "name": "Wheeler 300/50",
  "index_cache_id": "qdrant-index-cache-id",
  "ground_truth_set_id": "ground-truth-id",
  "retrieval": {
    "mode": "hybrid",
    "strategy": "chunk_retrieval",
    "top_k": 5,
    "candidate_k": 30,
    "parent_score": "max"
  },
  "reranking": null,
  "debug_level": "summary"
}
```

Optional user fields are `notes` and `parameter_set_id`. Enabled reranking accepts `enabled`,
`model_id`, and `params`. Authoritative snapshot/hash/data-manifest/code/result fields are not accepted;
extra create fields return HTTP 422. The response retains the SavedExperiment fields, including the
backend-generated `params_snapshot_json` (`raglab.saved_experiment.v1`) and configuration-only `params_hash`.
`code_commit` is populated by the backend at evaluation start, not supplied by the UI.

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
    "slice_metrics": {
      "hard": {
        "label": "Hard",
        "filter": {"difficulty": ["hard"]},
        "question_count": 3,
        "completed_question_count": 3,
        "error_count": 0,
        "metric_averages": {"page_recall_at_k": 0.5},
        "metric_question_counts": {"page_recall_at_k": 3},
        "warnings": []
      }
    },
    "questions": []
  }
}
```

Evaluation accepts no settings: omit the body or send `{}`. Supplying `index_cache_id` returns
HTTP 422; the saved `snapshot.index.cache_id` is always used. Only `created` may be claimed, atomically
at database level. Any already-running or terminal experiment returns HTTP 409. Failed attempts are
consumed and require a new experiment to retry. Required missing/hash-mismatched inputs are recorded
as failed evaluations. GT, chunks and required sparse statistics are loaded/verified once per attempt.

Metrics are currently returned in:

```text
SavedExperiment.metrics_summary_json
```

`MetricValue` remains part of the domain model for future normalized metric storage, but current GT
evaluation does not populate separate metric rows.

The current implementation of `POST /v1/projects/{project_id}/saved-experiments/{saved_experiment_id}/evaluate`
runs synchronously. It executes the resolved index/retrieval/reranking configuration
from `SavedExperiment.params_snapshot_json`, loops over the single verified in-memory canonical GT,
retrieves/reranks candidates, scores them with the existing single-question scorer, and stores:

```text
metrics_summary_json.evaluation
metrics_summary_json.metric_averages
metrics_summary_json.metric_question_counts
metrics_summary_json.slice_metrics (optional)
metrics_summary_json.questions
```

Per-question rows store metrics, warnings, error metadata, a compact `question_metadata` snapshot,
`ground_truth` expectations, and compact
`retrieved` top-k metadata. Retrieved metadata may include ids, source names, page numbers, ranks,
and scores, but must not store full chunk text unless a later explicit debug-full mode is added.
Rows may also store compact `usage` summaries for API stages, and `metrics_summary_json.evaluation.usage`
contains stage-level totals across the whole GT run.
The scorer can emit chunk-level metrics such as `hit_at_k`, `mrr_at_k`, and `recall_at_k`, and
page-oriented metrics such as `page_hit_at_k`, `page_mrr_at_k`, and `page_recall_at_k`. The Saved
Experiments list displays compact aggregate values and falls back from chunk-level keys to page-level
keys when needed. Declared slices are aggregated from those already-computed rows with the same metric
averager; an empty slice has `question_count: 0`, empty metric averages, and a warning. The saved
slice also records `completed_question_count`, `error_count`, and `metric_question_counts`: the
actual number of completed rows contributing a numeric value to each metric average. Failed rows
are excluded, never counted as retrieval metric zero. Different metric keys may have different
denominators (for example found versus not-found questions). Overall averages expose their counts
in the sibling `metric_question_counts` object using the same aggregation implementation.
Incomplete slices warn that metrics use completed rows only; slices with zero successful completions
have empty averages/count maps and an explicit no-successful-completions warning. Detail and Compare
show completed/total counts, errors, incomplete warnings, and each recorded metric denominator (`n`).
Old results lacking completion fields are labeled as not recorded, rather than assumed complete. The saved
experiment detail page is the canonical result view. Retrieval preview may
launch evaluation and link to the saved result, but should not duplicate the full per-question result
table inline.

## Breaking-Change Rule

After implementation, endpoint renames, required-field changes, response-shape changes, and
error-shape changes are breaking changes.
