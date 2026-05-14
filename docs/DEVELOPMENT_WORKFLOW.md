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

## Start services

```bash
docker compose up -d postgres qdrant
```

PostgreSQL is exposed on host port `5433` to avoid collisions with a local PostgreSQL install:

```text
DATABASE_URL=postgresql+psycopg://raglab:raglab@localhost:5433/raglab
```

## Start backend

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

Run database migrations before starting the backend against PostgreSQL:

```bash
alembic upgrade head
```

## Start UI

```bash
cd ui
npm install
npm run dev
```

## Run tests

```bash
python -m pytest
```

## Minimal manual workflow

```text
1. Create project
2. Upload source data asset
3. Inspect PDF/text-layer hints
4. Create prepared version by upload, `pymupdf_text`, or `docling`
5. Open Parameters and create a chunking ParameterSet with preview
6. Click Next or open Indexing to materialize chunks
7. Choose embedding, sparse, and Qdrant index settings
8. Create a dense, sparse, or hybrid Qdrant index cache
9. Run retrieval preview, creating a retrieval cache for the candidate set
10. Optionally rerank the current retrieval cache with different models or params
11. Register optional ground truth set
12. Save experiment with full parameter snapshot and data manifest hash
13. Inspect metrics
14. Compare saved experiments
15. Promote validated parameter snapshot later
```

The first local embedding and reranking models are SentenceTransformers models and may download model
weights on first use. Qdrant must be running before creating or previewing indexes.

## Review checklist

- docs updated;
- tests added or updated;
- no secrets committed;
- no real client data committed;
- configs are explicit;
- traces are inspectable.
