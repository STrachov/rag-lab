# Development Workflow

## Setup

```bash
py -3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
cp .env.example .env
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

## Start Services

```bash
docker compose up -d postgres qdrant
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

PostgreSQL is exposed on host port `5433`:

```text
DATABASE_URL=postgresql+psycopg://raglab:raglab@localhost:5433/raglab
```

Start the UI:

```bash
cd ui
npm install
npm run dev
```

## Run Tests

```bash
python -m pytest
```

The first local embedding and reranking models are SentenceTransformers models and may download
weights on first use. Qdrant must be running before creating or previewing indexes.

Voyage embedding models are remote catalog entries. To use them for indexing or retrieval preview,
set:

```bash
RAG_LAB_VOYAGE_API_KEY=...
```

`RAG_LAB_VOYAGE_BASE_URL` can override the default `https://api.voyageai.com` endpoint for testing.

## Minimal Manual Workflow

```text
1. Create project
2. Upload source data asset
3. Inspect PDF/text-layer hints
4. Select a registered preparation method and params
5. Create prepared data asset
6. Open Chunking and preview registered chunking strategies
7. Save reusable stage ParameterSets where useful
8. Materialize chunks
9. Optionally download a GT authoring pack
10. Create a dense, sparse, or hybrid Qdrant index cache
11. Run retrieval preview with manual questions or one GT question
12. Rerank the retrieval cache with different models or params
13. Register optional ground truth set
14. Save experiment with full parameter snapshot and prepared data manifest hash
15. Run async evaluation over all selected GT questions
16. Inspect metrics and failures
17. Compare saved experiments
18. Promote validated parameter snapshot later
```

## Test Coverage Guide

Use unit tests for:

```text
file inspection
preparation registries and adapters
parameter set create/delete protections
chunking strategy catalog and chunkers
token counting
embedding model registry
sparse model registry and BM25 vector building
Qdrant vector store adapter
hybrid retrieval fusion
reranker model registry and ordering
prompt rendering
citation building
evaluation metrics
recipe export
artifact writers
```

Use integration or smoke tests for:

```text
source upload -> inspection -> prepared version
document ingest -> chunk -> index -> retrieve
chunk materialization -> Qdrant index cache -> retrieval preview
chunk materialization -> GT authoring pack download
retrieval preview -> rerank candidates
retrieve -> answer trace
saved experiment -> async evaluation -> metrics
recipe promotion
```

Golden tests should use fixed synthetic documents and expected outputs, such as expected PDF
inspection, prepared Markdown, chunks, source-found retrieval, and not-found behavior.

## Review Checklist

```text
docs updated
tests added or updated where behavior changed
no secrets committed
no real client data committed
configs are explicit
derived cache/debug outputs are inspectable but not product-facing results
```
