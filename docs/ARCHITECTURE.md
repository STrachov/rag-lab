# Architecture

## High-Level Flow

```text
Project
-> source Data Asset
-> inspection and preparation parameters
-> prepared Data Asset
-> chunking/indexing/retrieval/reranking/generation parameters
-> optional Ground Truth Set
-> Saved Experiment
-> Metrics
```

Source data assets hold uploaded source files. Prepared data assets are RAG-ready versions linked to source data assets. File changes create `DataAssetManifest` snapshots; saved experiments snapshot the prepared data manifest hash used for the run.

The runtime pipeline may create chunks, embeddings, Qdrant indexes, retrieval traces, prompts, and answers. These are derived cache/debug outputs, not product-facing results.

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
- expose a backend-owned preparation method catalog;
- prepare source assets into prepared assets with adapter-backed methods such as `pymupdf_text` and `docling`;
- save reusable parameter sets;
- save optional ground truth set references;
- save experiments with full parameter snapshots;
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

Qdrant is not the application database. It is a vector index/cache backend used by experiment runtime code.

## UI

Use React/Vite.

The UI is a project workbench focused on:

```text
Projects
Data
Parameters
Ground Truth
Saved Experiments
Comparison
Settings
```

Debug views for chunks, traces, prompts, and answers may be added later, but they should be clearly marked as derived runtime/debug data.

The Data UI shows source assets as rows with linked prepared versions. Users can download files by original filename, add/delete files, delete assets, inspect PDF signals, and create prepared assets through a `Prepare with` method selector.

Docling is integrated as an external Docling Serve endpoint. Local CPU Docker, local GPU Docker, and remote GPU machines should use the same adapter boundary and differ by `RAG_LAB_DOCLING_BASE_URL`.

## Adapters

External services must be wrapped:

```text
Converter
Inspector
Preparer
Embedder
VectorStore
Reranker
LLM
Evaluator
```

This keeps Qdrant, OpenAI, local models, LlamaIndex, LangChain, Haystack, Ragas, and document conversion tools replaceable.
