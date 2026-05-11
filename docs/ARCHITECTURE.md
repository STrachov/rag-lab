# Architecture

## High-Level Flow

```text
Project
-> raw Data Asset
-> preparation parameters
-> prepared Data Asset
-> chunking/indexing/retrieval/reranking/generation parameters
-> optional Ground Truth Set
-> Saved Experiment
-> Metrics
```

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
  cache/
  manifests/
  ground_truth/
tests/
alembic/
```

## Backend

Use Python, FastAPI, SQLAlchemy 2.0, Alembic, and PostgreSQL.

Responsibilities:

- manage projects;
- register raw and prepared data assets;
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

## Adapters

External services must be wrapped:

```text
Converter
Embedder
VectorStore
Reranker
LLM
Evaluator
```

This keeps Qdrant, OpenAI, local models, LlamaIndex, LangChain, Haystack, Ragas, and document conversion tools replaceable.
