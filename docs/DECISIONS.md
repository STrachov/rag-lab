# Decisions

## Template

```markdown
## YYYY-MM-DD - Decision title

Status: proposed / accepted / deprecated

### Context

What problem are we solving?

### Decision

What did we decide?

### Alternatives considered

- Option A
- Option B

### Consequences

What becomes easier?
What becomes harder?
What should be revisited later?
```

---

## 2026-05-10 - Build RAG as a separate lab project

Status: accepted

### Context

OCRlty main is already a stable product-oriented document intelligence system. RAG work requires frequent experiments with chunking, retrieval, indexing, prompts, and eval.

### Decision

Create OCRlty RAG Lab as a separate experimental project. Move only validated recipes into OCRlty main.

### Consequences

Pros:
- experimentation does not overload OCRlty main;
- cleaner portfolio asset;
- easier client-specific testing.

Cons:
- some duplicated infrastructure at the start;
- later integration bridge may be needed.

---

## 2026-05-10 - Use frameworks as adapters

Status: accepted

### Context

LangChain, LlamaIndex, Haystack, and Ragas are useful, but they can make traces and experiment control opaque.

### Decision

Use project-native models for core entities. Use frameworks only as adapters.

### Consequences

Pros:
- clearer debugging;
- easier recipe export;
- less framework lock-in.

Cons:
- more initial code to write manually.

---

## 2026-05-11 - Use project-oriented model with metrics-only results

Status: accepted

### Context

The platform needs to be a permanent project-oriented RAG experimentation and evaluation system, not a dataset-first prototype or report generator.

### Decision

- The platform is organized around Project -> Data -> Chunking -> Retrieval -> Ground Truth -> Saved Experiments.
- Results are metrics only.
- Chunks, indexes, embeddings, traces, prompts, and generated answers are derived cache/debug outputs.
- Data preparation, including PDF-to-Markdown conversion method, is part of the parameter snapshot.

### Alternatives considered

- Use datasets as the top-level product concept.
- Store traces and generated answers as core experiment results.
- Make reports a first-class product model immediately.

### Consequences

Pros:
- clearer product model;
- easier comparison across saved experiments;
- less accidental persistence of sensitive derived data;
- conversion choices are reproducible.

Cons:
- debug output needs explicit opt-in;
- reporting will be derived later instead of being modeled now.

---

## 2026-05-12 - Use editable data assets with manifest snapshots

Status: accepted

### Context

Data assets need practical file management: source upload, add/delete files, download by original filename, PDF inspection, and prepared versions. Saved experiments still need to remain tied to the data state used at creation time.

### Decision

- Data assets may be edited by adding and deleting files.
- Each file change creates a `DataAssetManifest` snapshot in PostgreSQL.
- `DataAsset.manifest_hash` points to the current manifest.
- `SavedExperiment.data_asset_manifest_hash` snapshots the prepared data manifest used by the experiment.
- Uploaded and generated files are stored under generated safe filenames; original filenames live in manifest JSON.
- Source assets can have linked prepared versions.
- Source asset deletion also deletes linked prepared versions, but assets used by saved experiments cannot be deleted.
- The first preparation adapters are `pymupdf_text` for PDFs with text layers, `.txt`, and `.md`, plus `docling` through an external Docling Serve endpoint.

### Consequences

Pros:
- data management matches real experimentation workflows;
- manifest history is queryable and auditable in the application database;
- saved experiments remain tied to a specific data manifest;
- source files can be inspected before choosing a preparation path.

Cons:
- manifest snapshots are audit/history, not full file versioning after physical deletion;
- delete behavior must protect saved experiments;
- source/prepared relationships add UI complexity.

---

## 2026-05-13 - Use backend-driven parameter catalogs

Status: accepted

### Context

The Chunking workflow needs to compare multiple chunking methods, including native and
framework-backed implementations, without hardcoding method names and fields in the UI.

### Decision

- Parameter sets are categorized presets, starting with `chunking`.
- The Chunking UI loads chunking strategies from a backend-owned catalog.
- Each chunking strategy declares id, label, description, default params, field metadata, and the
  function that implements it.
- Framework implementations such as LangChain splitters are exposed as adapter-backed strategies
  while returning project-native chunk preview records.
- Chunking preview is computed debug output and is not stored as a product-facing result.
- Parameter sets can be deleted only when not referenced by saved experiments.

### Consequences

Pros:
- new chunking strategies can be added without frontend changes;
- native and library-backed splitters can be compared under one UI contract;
- saved parameter snapshots stay inspectable and categorized.

Cons:
- field metadata must remain stable enough for the UI;
- adapter-backed strategies add dependency management and version drift to watch later.

---

## 2026-05-14 - Use derived runtime caches for hybrid Qdrant retrieval

Status: accepted

### Context

After preparation and chunking, the lab needs an inspectable vertical slice for indexing and retrieval
without turning chunks, embeddings, indexes, or retrieval traces into product-facing experiment
results.

### Decision

- Materialize chunking snapshots into `DerivedCache(cache_type="chunks")` with normalized
  `raglab.chunks.v1` JSONL.
- Preserve parser-specific files such as Docling JSON as sidecar metadata rather than making them the
  internal chunk source of truth.
- Expose embedding and sparse model catalogs from the backend.
- Start with local SentenceTransformers embeddings for `intfloat/multilingual-e5-small` and
  `BAAI/bge-small-en-v1.5`, both CPU-capable.
- Start sparse retrieval with an inspectable local BM25-style model, `bm25_local`.
- Store Qdrant indexes as `DerivedCache(cache_type="qdrant_index")`.
- Use named Qdrant vectors: `dense` for embeddings and `sparse` for sparse vectors.
- Support dense, sparse, and hybrid retrieval preview; merge hybrid results with reciprocal rank
  fusion in application code.
- Store retrieval candidate sets as `DerivedCache(cache_type="retrieval_temp")`.
- Support optional reranking as a separate preview step over a retrieval cache and materialized chunk
  text.
- Record failed index creation attempts as `DerivedCache(status="failed")` with error metadata.

### Consequences

Pros:
- the UI can restore existing and failed indexes after navigation;
- dense, sparse, and hybrid retrieval can be compared before generation/evaluation exists;
- Qdrant remains a cache backend while PostgreSQL remains the application database;
- model and sparse params are inspectable and can later become saved experiment snapshots.

Cons:
- local embedding models introduce first-run model downloads and CPU latency;
- app-layer fusion is simple and transparent, but advanced hybrid tuning remains future work;
- local cross-encoder rerankers improve quality inspection but add latency and first-run model downloads;
- reranking parameters can be swept without repeating Qdrant retrieval;
- Qdrant collection compatibility is intentionally not preserved for old experimental collections.

---

## 2026-06-03 - Add explicit remote Voyage embedding adapters

Status: accepted

### Context

Local CPU SentenceTransformers embeddings are useful baselines, but they are slow enough to make
single experiment iteration painful. The lab needs faster production-relevant embedding candidates
while preserving reproducibility and data-safety visibility.

### Decision

- Keep local SentenceTransformers models as embedding baselines.
- Add `voyage_4_lite` and `voyage_4_large` as backend-driven embedding catalog entries.
- Treat Voyage as a remote embedding provider, not an internal domain model.
- Read credentials from `RAG_LAB_VOYAGE_API_KEY`.
- Use `input_type=document` for chunk embeddings and `input_type=query` for retrieval queries.
- Store selected Voyage params, including `output_dimension`, in the embedding snapshot.
- Use the snapshot `vector_size` when creating Qdrant named dense vectors.

### Alternatives considered

- Replace local embeddings with Voyage by default.
- Add a generic opaque external embedding chain.
- Store remote embeddings as product-facing results.

### Consequences

Pros:
- faster iteration for dense and hybrid indexes;
- stronger production-quality retrieval candidates;
- explicit provider and parameter snapshots remain inspectable.

Cons:
- chunk and query text leave the local machine when a Voyage model is selected;
- indexing now depends on external API availability, credentials, rate limits, and cost;
- Qdrant collections must be rebuilt when `output_dimension` changes.

---

## 2026-06-09 - Add explicit remote Voyage rerank adapters

Status: accepted

### Context

Local cross-encoder rerankers are useful baselines but can be slow on CPU and require first-run model
downloads. The lab needs production-relevant remote reranking candidates while keeping data movement
and rate limits visible.

### Decision

- Add `voyage_rerank_2_5` and `voyage_rerank_2_5_lite` to the backend reranker catalog.
- Treat Voyage reranking as an explicit remote API backend, not a replacement for local rerankers.
- Use the Voyage `/v1/rerank` contract with `query`, `documents`, `model`, `top_k`,
  `return_documents=false`, and `truncation`.
- Keep rerank rate-limit settings separate from embedding settings because Voyage exposes different
  TPM limits for rerank models.
- Show a compact frontend summary that remote reranking sends query and candidate text to the
  provider API.

### Consequences

Pros:
- faster and stronger reranking candidates are available without local model downloads;
- reranker parameter snapshots remain explicit and comparable;
- logs show request counts, estimated tokens, latency, retries, and rate-limit waits without logging
  chunk text or secrets.

Cons:
- query and candidate chunk text leave the local machine when a Voyage reranker is selected;
- reranking now depends on external API availability, credentials, rate limits, and cost;
- local token estimates remain approximate and may need conservative utilization on smaller plans.

---

## 2026-06-13 - Store full GT evaluation summaries on Saved Experiments

Status: accepted

### Context

Manual retrieval/reranking previews are useful for debugging one question, but choosing a recipe
requires running the same saved snapshot over every question in a ground truth set. Showing those
results inline on the Retrieval page makes the page too noisy and blurs previews with persisted
experiment results.

### Decision

- `SavedExperiment` remains the product-facing result entity.
- GT evaluation is launched from the Retrieval page for the selected Qdrant index and saved snapshot,
  but the canonical result view is the saved experiment detail page.
- The current evaluation implementation runs synchronously, retrieves and optionally reranks every
  linked GT question, and stores results in `metrics_summary_json`.
- `metrics_summary_json` stores aggregate `metric_averages`, run metadata under `evaluation`, and
  compact per-question rows under `questions`.
- Per-question rows may include ground-truth expectations, page references, retrieved ids, source
  names, page numbers, ranks, and scores, but not full chunk text.
- The Saved Experiments list stays compact with name/status, question count, Hit, MRR, Recall, and
  icon-only rename/delete actions.

### Consequences

Pros:
- evaluation results are durable and reachable from Saved Experiments;
- Retrieval stays focused on previews and launching evaluation;
- list metrics are scannable while detailed GT/retrieved comparisons remain available one click away;
- compact saved rows reduce accidental persistence of sensitive chunk text.

Cons:
- long evaluations currently hold the request open until completion;
- async/background execution may still be needed for larger GT sets or slow remote models;
- the list infers chunk-level versus page-level metrics from available metric keys until an explicit
  metric-family field is added.

---

## 2026-06-13 - Show full text for chunking preview chunks

Status: accepted

### Context

Chunking preview exists to judge chunk boundaries. Clipping the text inside each previewed chunk made
it impossible to see whether a chunk ended cleanly or swallowed unrelated context.

### Decision

Keep the `max_chunks` preview limit, but return the full text for each returned chunk in the existing
`text_preview` field for API compatibility. Remove the frontend `Preview chars` control.

### Consequences

Pros:
- chunk-boundary inspection is much more reliable;
- the number of returned preview chunks is still bounded.

Cons:
- chunking preview can expose more sensitive text on screen;
- users must treat screenshots and copied preview text as sensitive derived data.
