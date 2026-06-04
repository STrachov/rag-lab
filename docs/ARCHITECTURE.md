# Architecture

## High-Level Flow

```text
Project
-> source Data Asset
-> file inspection
-> preparation registry method + params
-> prepared Data Asset with provenance
-> stage registries/catalogs for chunking, indexing, retrieval, reranking, generation, evaluation
-> materialized chunks and Qdrant index cache
-> manual retrieval/reranking/generation previews
-> optional Ground Truth Set
-> Saved Experiment with full parameter snapshot
-> async evaluation
-> metrics
```

Source data assets hold uploaded source files. Prepared data assets are RAG-ready versions linked to source data assets. File changes create `DataAssetManifest` snapshots; saved experiments snapshot the prepared data manifest hash used for the run.

The runtime pipeline may create chunks, embeddings, Qdrant indexes, retrieval traces, prompts, and
answers. These are derived cache/debug outputs, not product-facing results. Saved experiment results
are metrics only.

The current runtime can materialize prepared data into normalized chunk JSONL under `data/cache/chunks/`, track that cache in PostgreSQL, build a Qdrant index cache with dense and optional sparse vectors, and run retrieval preview in dense, sparse, or hybrid mode. Dense embeddings can be created by local SentenceTransformers adapters or explicit remote Voyage adapters. Retrieval preview can optionally rerank retrieved candidates with local cross-encoder models. It returns retrieved chunk metadata, text previews, retrieval scores, and rerank score breakdowns; it is debug output, not experiment results.

## Recommended Structure

```text
app/
  api/
  db/
  models/
  services/
  adapters/
  core/
ui/
configs/
data/
  projects/
    {project_id}/
      source/
      prepared/
  cache/
    chunks/
    embeddings/
    sparse/
    qdrant_indexes/
    retrieval_temp/
    answer_temp/
  ground_truth/
tests/
alembic/
```

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
- render prompts and generated answers with citation/not-found behavior;
- save and delete categorized reusable parameter sets;
- save optional ground truth set references;
- save experiments with full parameter snapshots;
- run saved experiment evaluation asynchronously;
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
  Comparison
Admin
  Settings
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
parent id, and return full parent page or chapter context.

The Chunking UI owns chunking preview and reusable chunking `ParameterSet` creation. The Retrieval UI
materializes chunks, selects embedding, sparse, and reranker model parameters, creates Qdrant index
caches, lists existing/failed index caches, and previews retrieval. Saved Experiments owns full
snapshots, async evaluation status, metrics, and errors.

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

Current registry families:

```text
preparation methods
chunking strategies
embedding models
sparse retrieval models
reranking models
generation prompts/models
evaluation metrics/scorers
```

Preparation methods create prepared data assets. Other stage registries usually create reusable
parameter snapshots, previews, derived caches, or evaluation metrics.

Remote embedding catalog entries must make the provider explicit. Voyage entries require
`RAG_LAB_VOYAGE_API_KEY`, send chunk text as `input_type=document`, send retrieval queries as
`input_type=query`, and store the selected `output_dimension` in the embedding snapshot used to
create the Qdrant collection.

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
sparse
qdrant_index
retrieval_temp
answer_temp
```

Materialized chunk caches use `raglab.chunks.v1` JSONL with stable project-native fields. Parser
sidecars such as Docling JSON remain prepared data files or cache metadata; they are not the
internal source of truth.

Qdrant indexes are tracked as `DerivedCache(cache_type="qdrant_index")`. Qdrant is a cache backend,
not the application database. Failed index attempts should create `DerivedCache(status="failed")`
with inspectable error metadata.

Retrieval preview creates or reuses `DerivedCache(cache_type="retrieval_temp")` for the candidate
set. Reranking reads that retrieval cache plus full materialized chunk text, but full chunk text is
not stored in Qdrant payloads or retrieval temp metadata.
