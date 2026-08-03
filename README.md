# RAG Lab

Experimental workbench for building, comparing, evaluating, and documenting RAG pipelines over project data.

The project is not a generic chat-with-PDF demo. Its purpose is to run controlled experiments inside durable project workspaces and export production-ready RAG recipes after metrics are understood.

## Quick Start

### Prerequisites

- Python 3.12 or newer;
- Node.js with npm;
- Docker with Docker Compose.

### Windows PowerShell

Create the Python environment and install the backend:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Start PostgreSQL and Qdrant, then apply all database migrations:

```powershell
docker compose up -d postgres qdrant
alembic upgrade head
```

Start the backend:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

In a second PowerShell terminal, install and start the frontend:

```powershell
Set-Location ui
npm ci
npm run dev
```

### Linux And macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env

docker compose up -d postgres qdrant
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

In a second terminal:

```bash
cd ui
npm ci
npm run dev
```

Open:

- UI: `http://127.0.0.1:5173`;
- API documentation: `http://127.0.0.1:8080/docs`;
- health check: `http://127.0.0.1:8080/v1/health`.

Docling is optional for the initial launch. Start its local CPU service when Docling preparation is
needed:

```bash
docker compose --profile docling up -d docling
```

### Checks

Run backend tests from the repository root:

```powershell
python -m pytest
```

Build the frontend:

```powershell
Set-Location ui
npm run build
```

Remote Voyage and OpenAI models require API keys and optional rate/cost settings. Docling deployment
options, provider configuration, troubleshooting, and the complete manual workflow are documented in
[`docs/DEVELOPMENT_WORKFLOW.md`](docs/DEVELOPMENT_WORKFLOW.md).

## Current Scope

The implemented vertical slice covers project/data management, preparation, chunking, Qdrant
indexing, retrieval/reranking previews, ground truth, synchronous saved-experiment evaluation, and
inline experiment comparison.

Generation, grounded answers/citations, promoted recipe export, background evaluation, authentication,
and production deployment hardening are not implemented. The Settings page and the generic
`/v1/ask`, `/v1/retrieve`, and `/v1/experiments` endpoints are placeholders/reserved stubs.

The target product invariant is a self-contained full parameter snapshot. Current UI-created saved
experiments store the prepared-data manifest hash, index-cache reference, retrieval settings, optional
reranking settings, and GT reference. Chunking/embedding/sparse/preparation lineage is still indirect
through data-asset and derived-cache metadata, and the UI does not populate `code_commit`. See
[`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) for the exact implementation boundary.

## Product Flow

Core flow:

```text
Project
-> Source Data Asset
-> Preparation method and parameters
-> Prepared Data Asset
-> Data Asset Manifest snapshot
-> categorized Parameter Set
-> DerivedCache chunks
-> Qdrant index cache
-> retrieval preview
-> retrieval_temp candidate cache
-> optional reranking preview
-> optional Ground Truth Set
-> Saved Experiment with current evaluation snapshot and data manifest hash
-> ground-truth evaluation metrics
-> metrics comparison
-> validated parameter choice
```

In the UI, create or open a project first. The Data, Preparation, Chunking, Retrieval, Ground Truth,
and Saved Experiments sections then operate inside that current project context. Metrics comparison
is available inside Saved Experiments.

Current implemented foundation:

- editable active/archived projects with server-side status filtering;
- project-scoped source and prepared data assets with manifest snapshots;
- preparation through upload, `pymupdf_text`, or Docling Serve;
- backend-driven chunking strategy catalog;
- Chunking Lab with preview over prepared data assets;
- materialized chunk caches with normalized chunk metadata;
- downloadable ground-truth authoring packs with prepared text, chunks, schema, template, and instructions;
- backend-driven embedding and sparse retrieval model catalogs;
- backend-driven reranker model catalog;
- Qdrant indexing with dense and local BM25-style sparse vectors for dense, sparse, and hybrid retrieval preview;
- optional reranking over retrieved candidates with local cross-encoder, remote Voyage, or OpenAI LLM-as-reranker models;
- editable API reranker cost assumptions with usage and estimated cost summaries;
- full ground-truth evaluation over all questions in a Ground Truth Set;
- saved experiment detail pages with aggregate metrics, API reranking usage totals, and per-question result summaries;
- saved experiment rename/delete actions and compact list metrics for questions, Hit, MRR, and Recall;
- categorized parameter sets with protected deletion;
- saved experiments that snapshot prepared data manifest hashes plus current evaluation settings and
  references; making the snapshot self-contained is still required work.

Start with these files:

1. `docs/CURRENT_STATE.md`
2. `docs/PRODUCT_SPEC.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DOMAIN_MODEL.md`
5. `docs/API_CONTRACTS.md`
6. `docs/DEVELOPMENT_WORKFLOW.md`
7. `docs/DECISIONS.md`
8. `docs/DATA_POLICY.md`
