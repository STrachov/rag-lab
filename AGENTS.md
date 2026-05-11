# AGENTS.md

## Role Of This Repository

This repository is a permanent project-oriented RAG experimentation and evaluation platform. It is not a generic chatbot, not a LangChain demo, and not a report-first product.

The main goal is to test RAG strategies inside durable projects and preserve the data references, parameter snapshots, optional ground truth references, and metrics needed to choose a production-ready recipe.

## Core Rules For AI Coding Agents

- Prefer transparent, inspectable code over opaque framework chains.
- Use frameworks as adapters, not as the project domain model.
- Do not make LangChain `Document` or LlamaIndex `Node` the internal source of truth.
- Use `Project`, `DataAsset`, `ParameterSet`, `GroundTruthSet`, `SavedExperiment`, `MetricValue`, and `DerivedCache` as core entities.
- Do not use `Dataset` as the main product concept; use `Data Asset` or `Data`.
- Do not introduce `ExperimentRun` as a separate main concept; use `SavedExperiment`.
- Do not use `Report` as a main concept yet; reports may be derived later from saved experiment metrics.
- Do not use `Artifact` as a product-facing concept; artifacts are technical files/cache only.
- Treat results as metrics only.
- Treat chunks, embeddings, Qdrant indexes, retrieval traces, prompts, and generated answers as derived runtime/cache/debug outputs unless debug mode explicitly requests persistence.
- Include data preparation, including PDF-to-Markdown/OCR/conversion method and settings, in parameter snapshots.
- Keep experiment results reproducible.
- Do not add GraphRAG, agents, or complex orchestration unless explicitly requested.
- Do not build a polished SaaS UI before the experiment workflow is stable.

## Core Product Model

```text
Project
  Data
    raw data
    prepared data
  Parameter Sets
    preparation
    chunking
    indexing
    retrieval
    reranking
    generation
  Ground Truth
    optional
  Saved Experiments
    data reference
    full parameter snapshot
    optional ground truth reference
    results = metrics only
```

## Done Criteria

A feature is not complete unless at least one is true:

- it has a test;
- it creates or updates an inspectable metric, parameter snapshot, or data reference;
- it appears in a saved experiment as metrics;
- it is documented in the relevant markdown file.

## Data Safety

Never commit real client data, API keys, auth headers, private URLs, PII, PHI, financial data, unredacted documents, or derived cache from sensitive data.
