# Architecture

## High-Level Flow

```text
Project
-> source Data Asset
-> file inspection
-> preparation registry method + params
-> prepared Data Asset with provenance
-> stage registries/catalogs for chunking, indexing, retrieval, reranking, evaluation
-> materialized chunks and Qdrant index cache
-> manual retrieval/reranking previews
-> optional Ground Truth Set
-> Saved Experiment with full parameter snapshot
-> ground-truth evaluation
-> metrics
```

The backend generates self-contained pipeline metadata through historical index/chunks/data lineage;
see [REPRODUCIBILITY.md](REPRODUCIBILITY.md). Source/prepared contents remain in DataAsset storage.
Saved experiments use the manifest identified by the index, not a later current DataAsset manifest.

The runtime pipeline may create chunks, embeddings, Qdrant indexes, retrieval traces, prompts, and
answers. These are derived cache/debug outputs, not product-facing results. Saved experiment results
are metrics only.

The current runtime can materialize prepared data into normalized chunk JSONL under `data/cache/chunks/`, track that cache in PostgreSQL, build a Qdrant index cache with dense and optional sparse vectors, and run retrieval preview in dense, sparse, or hybrid mode. Dense embeddings can be created by local SentenceTransformers adapters or explicit remote Voyage adapters. Retrieval preview can optionally rerank retrieved candidates with local cross-encoder, remote Voyage, or OpenAI pointwise LLM rerankers. It returns retrieved chunk metadata, clipped retrieval text previews, retrieval scores, rerank score breakdowns, and optional API usage/cost summaries; it is debug output, not experiment results. Chunking preview is a separate debug view and returns full text for the previewed chunks.

## Code And Runtime Storage

```text
app/
  api/
  db/
  models/
  services/
  adapters/
  core/
ui/
data/
  projects/
    {project_id}/
      source/
        {data_asset_id}/
          _manifest.json
          files/
      prepared/
        {data_asset_id}/
          _manifest.json
          files/
  cache/
    chunks/
    sparse/
  ground_truth/
    {project_id}/
      ground_truths/
tests/
alembic/
```

This is the current local filesystem shape, not a requirement that every cache type has a directory.
Qdrant vectors live in Qdrant collections; Qdrant-index and retrieval-temp state is tracked through
PostgreSQL `DerivedCache` metadata. The filesystem currently stores chunk JSONL/manifest files and
sparse BM25 statistics. `embeddings` and `answer_temp` remain reserved API cache types.

## Backend

Use Python, FastAPI, SQLAlchemy 2.0, Alembic, and PostgreSQL.

Responsibilities:

- manage projects;
- upload, inspect, edit, and delete source and prepared data assets;
- store data asset manifest snapshots;
- expose backend-owned stage registries/catalogs;
- prepare source assets into prepared assets with adapter-backed methods such as `pymupdf_text` and `docling`;
- preview chunking over prepared data assets without storing product-facing results;
- materialize chunks from prepared data into `DerivedCache(cache_type="chunks")`;
- build Qdrant index caches with named dense vectors and optional BM25-style sparse vectors;
- preview dense, sparse, and hybrid retrieval over Qdrant index caches;
- rerank retrieval preview candidates from full materialized chunk text;
- save and delete categorized reusable parameter sets;
- save optional ground truth set references;
- save experiments with backend-generated historical lineage and effective configuration snapshots;
- run saved experiment evaluation over linked ground truth questions;
- store metrics-only results;
- track derived cache entries;
- wrap external systems behind adapters.

## Application Database

PostgreSQL is the primary application database. It stores product state:

```text
Project
DataAsset
DataAssetManifest
ParameterSet
GroundTruthSet
SavedExperiment
MetricValue
DerivedCache
```

Qdrant is not the application database. It is a vector index/cache backend used by experiment runtime code. PostgreSQL stores the `DerivedCache` reference, cache key, parameter hash, collection name, status, and metadata needed to inspect or rebuild the index.

## UI

Use React/Vite.

The UI is a project workbench focused on:

```text
Project
  Projects
  Data
  Ground Truth
Pipeline
  Preparation
  Chunking
  Retrieval
Evaluation
  Saved Experiments
Admin
  Settings (placeholder)
```

Debug views for chunks, traces, prompts, and answers may be added later, but they should be clearly marked as derived runtime/debug data.

The Data UI shows source assets as rows with linked prepared versions. Users can download files by
original filename, add/delete files, delete assets, and inspect PDF signals.

Preparation is an explicit Pipeline page after upload. It uses the backend preparation method
catalog, creates `ParameterSet(category="preparation")` presets when requested, and materializes
prepared data assets from source assets.

Docling preparation may materialize parent-unit sidecars (`*.pages.jsonl` and `*.chapters.jsonl`).
The `page_recursive` and `chapter_recursive` chunking strategies use those sidecars to create child
chunks with parent metadata. Parent retrieval strategies then retrieve child chunks, aggregate by
parent id, and return parent page or chapter previews clipped to 1,200 characters (also the current parent reranking input).

The Chunking UI owns chunking preview, reusable chunking `ParameterSet` creation, materialized chunk
caches, GT authoring-pack download, and routing selected chunks into Retrieval. The Retrieval UI
selects embedding, sparse, and reranker model parameters, creates Qdrant index caches, lists
existing/failed index caches, previews retrieval/reranking, and can launch GT evaluation for the
currently selected index. Saved Experiments owns full snapshots, rename/delete, compact aggregate
metrics, detail pages, per-question evaluation summaries, errors, and inline comparison. Comparison
is implemented as a derived UI view over selected saved experiments; it does not create a new backend
product entity or persist comparison results.

Question metadata and evaluation-slice definitions live in canonical GroundTruthSet JSON. Evaluation
retrieves/reranks each question once, snapshots question metadata into the compact result row, and
uses one aggregate function for both overall and slice metrics in
`SavedExperiment.metrics_summary_json`. The comparison UI treats equal slice ids with different
filter definitions as non-comparable. No slice entity, table, or additional model call is introduced.

## Registries And Catalogs

Registries are backend-owned contracts used to render UI controls and validate stage parameters.
Adding a new registered method should not require hardcoding ids or field ranges in the frontend.

Registry entries should include:

```text
id
label
description
default params
field metadata
validation rules
implementation adapter/function
version/provenance where relevant
```

Current backend-driven registry/catalog families:

```text
preparation methods
chunking strategies
embedding models
sparse retrieval models
reranking models
```

Current indexing modes and retrieval strategies are backend-validated contracts, but are not exposed
through independent field catalogs. Planned registry families are:

```text
generation prompts/models
evaluation metrics/scorers
```

Generation prompts/models and evaluation metric catalogs are roadmap registry families; they are not
implemented as current API/UI catalogs. Ground-truth scoring itself is implemented as backend service
logic and is used by preview scoring and saved-experiment evaluation.

Preparation methods create prepared data assets. Other stage registries usually create reusable
parameter snapshots, previews, derived caches, or evaluation metrics.

Remote embedding catalog entries must make the provider explicit. Voyage entries require
`RAG_LAB_VOYAGE_API_KEY`, send chunk text as `input_type=document`, send retrieval queries as
`input_type=query`, and store the selected `output_dimension` in the embedding snapshot used to
create the Qdrant collection.

Remote reranker catalog entries must also make the provider explicit. Voyage rerank entries use the
same API key and base URL, send the query plus current candidate text to `/v1/rerank`, and use
separate RPM/TPM throttle settings because Voyage embedding and rerank limits differ.

The OpenAI LLM reranker uses Chat Completions with strict JSON relevance scores, configurable
candidate batching/clipping, and optional blending with the normalized retrieval score. It is a
reranking adapter only; answer generation is not implemented. Local SentenceTransformer embedders
and cross-encoder rerankers are cached in process by normalized model parameters to avoid repeated
model loading.

Docling is integrated as an external Docling Serve endpoint. Local CPU Docker, local GPU Docker, and remote GPU machines should use the same adapter boundary and differ by `RAG_LAB_DOCLING_BASE_URL`.

## Adapters

External services must be wrapped:

```text
Converter
Inspector
Preparer
Embedder
SparseRetriever
VectorStore
Reranker
LLM
Evaluator
```

This keeps Qdrant, OpenAI, local models, LlamaIndex, LangChain, Haystack, Ragas, and document conversion tools replaceable.

## Derived Cache

Derived cache may include:

```text
chunks
embeddings
qdrant_index
retrieval_temp
answer_temp
```

Sparse/BM25 support is currently represented inside qdrant-index metadata, including sparse vector
configuration and `sparse_stats_path`; it is not exposed as a standalone `DerivedCache` type.

Materialized chunk caches use `raglab.chunks.v1` JSONL with stable project-native fields. Parser
sidecars such as Docling JSON remain prepared data files or cache metadata; they are not the
internal source of truth.

Qdrant indexes are tracked as `DerivedCache(cache_type="qdrant_index")`. Qdrant is a cache backend,
not the application database. Failed index attempts should create `DerivedCache(status="failed")`
with inspectable error metadata.

Retrieval preview creates or reuses `DerivedCache(cache_type="retrieval_temp")` for the candidate
set. Reranking reads that retrieval cache plus full materialized chunk text, but full chunk text is
not stored in Qdrant payloads or retrieval temp metadata.
