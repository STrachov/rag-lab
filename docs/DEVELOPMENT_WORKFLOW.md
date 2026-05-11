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
python -m pip install -e .[dev]
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
2. Register raw data asset
3. Create preparation and RAG parameter sets
4. Register optional ground truth set
5. Save experiment with full parameter snapshot
6. Inspect metrics
7. Compare saved experiments
8. Promote validated parameter snapshot later
```

## Review checklist

- docs updated;
- tests added or updated;
- no secrets committed;
- no real client data committed;
- configs are explicit;
- traces are inspectable.
