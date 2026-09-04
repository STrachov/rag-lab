# Current State

Last verified against the tracked codebase: 2026-09-04.

This document is the source of truth for what is implemented now. `PRODUCT_SPEC.md` describes the
target product, `ARCHITECTURE.md` describes the design boundaries, and `API_CONTRACTS.md` describes
the current UI/backend contract.

## Implemented

### Projects

Create, list, open, edit, archive/restore, and filter by lifecycle status.

### Data

Upload source/prepared assets, inspect files, edit file sets, download files, and delete with
reference protection. Manifest snapshots are stored in PostgreSQL.

### Preparation

Backend-driven `pymupdf_text` and Docling methods, preparation presets, provenance, and optional
Docling page/chapter sidecars.

### Chunking

Backend-driven native and LangChain-adapter strategies, full-text preview, materialized
`raglab.chunks.v1` caches, and GT authoring-pack export.

### Indexing And Retrieval

Dense, sparse, and hybrid Qdrant indexes; local or Voyage embeddings; chunk and parent-unit
retrieval previews.

### Reranking

Local cross-encoders, Voyage rerankers, and an OpenAI pointwise LLM reranker. Remote usage and
estimated cost summaries are supported.

### Ground Truth

JSON/JSONL upload, canonicalization, chunk-level and page-level judgments, one-question preview
scoring, downloadable source/canonical files, optional per-question metadata, and declarative
evaluation slices. Metadata and slice definitions remain part of the canonical GT content.

### Saved Experiments

Create, rename, delete, synchronously evaluate all linked GT questions, inspect aggregate/per-question
results, and compare selected experiments inline. One evaluation pass now produces overall metrics
plus declared slice metrics from the same per-question results; detail rows can be filtered by the
metadata snapshot stored at evaluation time.

### Metrics

Retrieval metrics are stored in `SavedExperiment.metrics_summary_json`; `MetricValue` rows are not
populated by the current evaluation path.

## Partial Or Reserved

### Experiment Reproducibility

The product invariant is a self-contained full parameter snapshot. The current UI-created snapshot
stores the index-cache id/key plus retrieval, reranking, and GT settings. Chunking, embedding, sparse,
and preparation lineage remain indirect through the referenced data asset and `DerivedCache`
metadata. `code_commit` is not populated by the UI. Do not call the current record independently
reproducible after its referenced caches are removed.

### Evaluation Execution

Evaluation runs synchronously in the API request. There is no background worker, queue,
cancellation, or progress endpoint.

### Settings

The route and navigation entry exist, but the page is a placeholder. Runtime settings come from
environment variables.

### Generic Runtime Endpoints

`POST /v1/ask`, `POST /v1/retrieve`, and `POST /v1/experiments` are reserved stubs that return HTTP
501. Project-scoped retrieval preview and saved-experiment APIs are the implemented paths.

### Cache Types

The API schema reserves `embeddings` and `answer_temp`; current runtime creation paths use `chunks`,
`qdrant_index`, and `retrieval_temp`. Sparse statistics are files referenced by Qdrant-index metadata.

## Not Implemented

- answer generation and grounded citations;
- generation/prompt and evaluation-metric catalogs;
- promoted recipe entities or recipe export;
- authentication, authorization, multi-user isolation, or production deployment hardening;
- frontend automated tests;
- automated integration tests against live PostgreSQL, Qdrant, Docling, Voyage, or OpenAI services.

## Verification Baseline

The repository currently contains 95 Python test functions; all 95 passed in the verification run
for this update. API tests use an in-memory SQLite database and fake runtime adapters where external
systems are involved. The supported checks are:

```powershell
python -m pytest
Set-Location ui
npm ci
npm run build
```

Live Qdrant, Docling, Voyage, and OpenAI behavior still requires explicit manual/integration
verification with synthetic or approved data.
