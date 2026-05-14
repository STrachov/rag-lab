# AGENTS.md

## Role Of This Repository

This repository is a permanent project-oriented RAG experimentation and evaluation platform. It is not a generic chatbot, not a LangChain demo, and not a report-first product.

The main goal is to test RAG strategies inside durable projects and preserve the data references, parameter snapshots, optional ground truth references, and metrics needed to choose a production-ready recipe.

## Core Rules For AI Coding Agents

- Prefer transparent, inspectable code over opaque framework chains.
- Use frameworks as adapters, not as the project domain model.
- Do not make LangChain `Document` or LlamaIndex `Node` the internal source of truth.
- Use `Project`, `DataAsset`, `DataAssetManifest`, `ParameterSet`, `GroundTruthSet`, `SavedExperiment`, `MetricValue`, and `DerivedCache` as core entities.
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
    source/raw data
    prepared data versions
    manifest snapshots
  Parameter Sets
    category-scoped reusable presets
    chunking
    embedding
    indexing
    retrieval
    reranking
    generation
    evaluation
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

## Current Implementation Notes

- Source and prepared data assets are editable and tracked with manifest snapshots.
- Preparation provenance belongs to prepared data assets; the Chunking/Retrieval workflow should not re-edit already-applied preparation settings.
- Parameter sets have a `category` such as `chunking`, `embedding`, `indexing`, `retrieval`, `generation`, `evaluation`, or `general`.
- Chunking strategies are backend-driven. The UI must load the strategy catalog instead of hardcoding strategy names or fields.
- Chunking preview is derived debug output, not a saved experiment result. A chunking snapshot may also be materialized into `DerivedCache(cache_type="chunks")` for later indexing.
- Embedding and sparse retrieval models are backend-driven catalogs. Current local models include `intfloat/multilingual-e5-small`, `BAAI/bge-small-en-v1.5`, and `bm25_local`.
- Reranking models are backend-driven catalogs. Current local rerankers include `BAAI/bge-reranker-v2-m3`, `Qwen/Qwen3-Reranker-0.6B`, and `cross-encoder/ms-marco-MiniLM-L6-v2`.
- Qdrant indexes are derived cache entries. Current Qdrant collections use named vectors (`dense`, optional `sparse`) and support `dense`, `sparse`, and `hybrid` retrieval previews.
- Retrieval preview is derived debug output. It may show source metadata, retrieval scores, rerank scores, and clipped chunk text, but it is not a saved experiment result.
- Runtime failures that matter for reproducibility, such as failed Qdrant indexing, should be recorded as `DerivedCache(status="failed")` with inspectable error metadata.

## Data Safety

Never commit real client data, API keys, auth headers, private URLs, PII, PHI, financial data, unredacted documents, or derived cache from sensitive data.
