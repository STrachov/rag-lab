# Project Brief

## Purpose

RAG Lab is a permanent project-oriented platform for experimenting with, evaluating, and documenting RAG systems over document data.

It answers questions such as:

- Which data preparation method works best for this project?
- Which chunking, indexing, retrieval, reranking, and generation parameters are worth keeping?
- Are answers grounded in retrieved evidence?
- Can the system correctly say "not found"?
- Which parameter snapshot should be reused in production?

## Core Product Model

```text
Project
  Data Assets
    source data
    prepared versions
    manifest snapshots
  Parameter Sets
    chunking
    embedding
    indexing
    retrieval
    reranking
    generation
    evaluation
  Ground Truth Sets
    optional
  Saved Experiments
    data reference
    data manifest hash
    full parameter snapshot
    optional ground truth reference
    results = metrics only
```

## What This Project Is

- RAG experimentation and evaluation platform
- Project workspace for data, parameters, ground truth, and saved experiments
- Source data upload, lightweight inspection, and prepared data versioning
- Backend-driven preparation and chunking method catalogs
- Chunking parameter preview before saving reusable parameter sets
- Backend-driven embedding and sparse retrieval model catalogs
- Backend-driven reranker model catalog
- Derived chunk materialization and Qdrant index caches
- Dense, sparse, hybrid, and reranked retrieval debugging workbench
- Retrieval preview with retrieved chunk text previews and score breakdowns
- Metrics comparison tool
- Production recipe generator after enough experiments are validated

## What This Project Is Not

- Generic chatbot
- Full SaaS product
- Agent platform
- GraphRAG-first system
- Document conversion product by itself

## Results

Saved experiment results are metrics only:

- quality metrics
- retrieval metrics
- citation metrics
- latency and cost metrics
- optional manual or LLM-judge scores

Chunks, embeddings, Qdrant indexes, retrieval traces, prompts, and generated answers are derived runtime/cache/debug outputs by default. Persist them only when a debug mode explicitly requests it.

Materialized chunks and Qdrant indexes are tracked as `DerivedCache` entries. Current Qdrant indexes store named dense vectors and optional local BM25-style sparse vectors so dense, sparse, hybrid, and reranked retrieval can be compared before saved experiment metrics exist.

## Relationship to OCRlty Main

```text
RAG Lab:
  projects, data assets, manifest snapshots, parameter snapshots, ground truth, saved experiments, metrics

OCRlty main:
  stable product features and production document workflows
```

Only validated recipes or parameter snapshots should move from RAG Lab to OCRlty main.
