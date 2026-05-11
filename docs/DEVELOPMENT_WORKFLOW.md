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
docker compose up -d qdrant
```

## Start backend

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
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
1. Create dataset
2. Add sample documents
3. Run chunking
4. Build index
5. Run retrieval playground
6. Run answer playground
7. Create eval set
8. Run experiment
9. Inspect failure cases
10. Export recipe
```

## Review checklist

- docs updated;
- tests added or updated;
- no secrets committed;
- no real client data committed;
- configs are explicit;
- traces are inspectable.
