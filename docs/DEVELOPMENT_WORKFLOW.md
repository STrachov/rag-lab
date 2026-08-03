# Development Workflow

## Setup

```bash
python3.12 -m venv .venv
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
npm ci
npm run dev
```

Start optional local Docling Serve only when Docling preparation is needed:

```bash
docker compose --profile docling up -d docling
```

## Run Tests

```bash
python -m pytest
```

The backend tests use an in-memory SQLite database and fake adapters for Qdrant/remote providers;
they are not live-service integration tests. The UI currently has no automated test suite. Verify
the production frontend build separately:

```bash
cd ui
npm ci
npm run build
```

The first local embedding and reranking models are SentenceTransformers models and may download
weights on first use. Qdrant must be running before creating or previewing indexes.

Voyage embedding models are remote catalog entries. To use them for indexing or retrieval preview,
set:

```bash
RAG_LAB_VOYAGE_API_KEY=...
```

`RAG_LAB_VOYAGE_BASE_URL` can override the default `https://api.voyageai.com` endpoint for testing.
The default Voyage throttle matches the current paid `voyage-4-lite` limits:

```bash
RAG_LAB_VOYAGE_RPM_LIMIT=2000
RAG_LAB_VOYAGE_TPM_LIMIT=16000000
RAG_LAB_VOYAGE_TPM_UTILIZATION=0.95
RAG_LAB_VOYAGE_MAX_RETRIES=5
```

Voyage reranker models use the same `RAG_LAB_VOYAGE_API_KEY` and base URL, but have separate
throttle settings because the account limits differ by endpoint/model:

```bash
RAG_LAB_VOYAGE_RERANK_RPM_LIMIT=2000
RAG_LAB_VOYAGE_RERANK_2_5_TPM_LIMIT=2000000
RAG_LAB_VOYAGE_RERANK_2_5_LITE_TPM_LIMIT=4000000
RAG_LAB_VOYAGE_RERANK_TPM_UTILIZATION=0.95
RAG_LAB_VOYAGE_RERANK_MAX_RETRIES=5
```

Tune these to match the active Voyage project limits. `RAG_LAB_VOYAGE_TPM_UTILIZATION`
keeps batch planning below the advertised TPM limit because local token estimates are approximate.
For a free-plan `voyage-4-lite` account, use:

```bash
RAG_LAB_VOYAGE_RPM_LIMIT=3
RAG_LAB_VOYAGE_TPM_LIMIT=10000
RAG_LAB_VOYAGE_TPM_UTILIZATION=0.65
```

`429 Too Many Requests` responses are
retried with backoff and `Retry-After` support; `403 Forbidden` usually points to an IP, VPN, proxy,
or Voyage project access restriction rather than a batching issue.
On low limits, indexing may take several minutes because requests are paced by RPM and TPM. If Voyage
still returns `429`, wait for the Voyage quota window to reset or lower `RAG_LAB_VOYAGE_TPM_UTILIZATION`.
If Voyage returns a read timeout, use a higher embedding `timeout_seconds` value such as 300-600 and
consider lowering `batch_size` for unstable VPN/proxy connections.

OpenAI LLM-as-reranker uses Chat Completions with strict JSON output. To use
`openai_llm_reranker`, set:

```bash
RAG_LAB_OPENAI_API_KEY=...
RAG_LAB_OPENAI_BASE_URL=https://api.openai.com
RAG_LAB_OPENAI_LLM_RERANK_MODEL=gpt-5.4-mini
RAG_LAB_OPENAI_LLM_RERANK_MODEL_OPTIONS=gpt-5.4-mini,gpt-5.4-nano
RAG_LAB_OPENAI_MAX_RETRIES=2
```

The concrete OpenAI model is a reranker parameter named `model`. The backend catalog exposes it as a
select field using `RAG_LAB_OPENAI_LLM_RERANK_MODEL_OPTIONS`; change that env value when the active
OpenAI project uses a different available model list.
API reranking previews and GT evaluations record compact usage summaries. The current application
defaults are shown below; override them to match the provider prices you actually use:

```bash
RAG_LAB_OPENAI_LLM_RERANK_INPUT_COST_PER_1M_TOKENS=0.2
RAG_LAB_OPENAI_LLM_RERANK_OUTPUT_COST_PER_1M_TOKENS=1.25
RAG_LAB_VOYAGE_RERANK_2_5_COST_PER_1M_TOKENS=0.05
RAG_LAB_VOYAGE_RERANK_2_5_LITE_COST_PER_1M_TOKENS=0.02
```

OpenAI cost uses provider-reported prompt/completion tokens. Voyage rerank cost uses the same local
token estimate used for throttling, so treat it as an approximation. Provider pricing can change;
verify these local assumptions before using cost comparisons. These values become editable
reranker params in the UI and are saved in experiment snapshots.

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
14. Save experiment with the current evaluation snapshot and prepared data manifest hash
15. Run GT evaluation over all selected GT questions
16. Open the saved experiment detail page to inspect aggregate metrics, per-question summaries, and failures
17. Compare saved experiments
```

The current manual product workflow ends at comparison. Self-contained cache/data/code lineage,
background evaluation, generation, and recipe promotion/export are follow-up implementation work.

## Test Coverage Guide

Current automated coverage includes:

```text
file inspection
preparation registries and adapters
project lifecycle and filtering
data asset manifest/edit/delete protections
parameter set create/delete protections
chunking strategy catalog and chunkers
Docling page/chapter parent units
embedding model registry
sparse model registry and BM25 vector building
Qdrant cache contracts through fake adapters
dense/sparse/hybrid and parent retrieval
local, Voyage, and OpenAI reranker contracts
chunk materialization -> GT authoring pack download
chunk-level and page-level ground truth metrics
saved experiment -> GT evaluation -> metrics
saved experiment rename/delete and failure summaries
```

Still required when those features are implemented:

```text
frontend component/interaction tests
live PostgreSQL and Qdrant integration tests
Docling/Voyage/OpenAI opt-in integration tests with approved synthetic data
prompt rendering and versioning
citation building and grounded-answer behavior
not-found answer behavior
recipe promotion/export
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
