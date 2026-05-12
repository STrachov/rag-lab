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
    preparation
    chunking
    indexing
    retrieval
    reranking
    generation
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
- Retrieval and answer debugging workbench
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

## Relationship to OCRlty Main

```text
RAG Lab:
  projects, data assets, manifest snapshots, parameter snapshots, ground truth, saved experiments, metrics

OCRlty main:
  stable product features and production document workflows
```

Only validated recipes or parameter snapshots should move from RAG Lab to OCRlty main.
