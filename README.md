# RAG Lab

Experimental workbench for building, comparing, evaluating, and documenting RAG pipelines over project data.

The project is not a generic chat-with-PDF demo. Its purpose is to run controlled experiments inside durable project workspaces and export production-ready RAG recipes after metrics are understood.

Core flow:

```text
Project
-> Source Data Asset
-> Preparation method and parameters
-> Prepared Data Asset
-> Data Asset Manifest snapshot
-> categorized Parameter Set
-> DerivedCache chunks
-> Qdrant index cache
-> retrieval preview
-> retrieval_temp candidate cache
-> optional reranking preview
-> optional Ground Truth Set
-> Saved Experiment with full parameter snapshot
-> ground-truth evaluation metrics
-> metrics comparison
-> validated recipe
```

In the UI, create or open a project first. The Data, Preparation, Chunking, Retrieval, Ground Truth,
Saved Experiments, and Comparison sections then operate inside that current project context.

Current implemented foundation:

- project-scoped source and prepared data assets with manifest snapshots;
- preparation through upload, `pymupdf_text`, or Docling Serve;
- backend-driven chunking strategy catalog;
- Chunking Lab with preview over prepared data assets;
- materialized chunk caches with normalized chunk metadata;
- downloadable ground-truth authoring packs with prepared text, chunks, schema, template, and instructions;
- backend-driven embedding and sparse retrieval model catalogs;
- backend-driven reranker model catalog;
- Qdrant indexing with dense and local BM25-style sparse vectors for dense, sparse, and hybrid retrieval preview;
- optional reranking over retrieved candidates with local cross-encoder or remote Voyage models;
- full ground-truth evaluation over all questions in a Ground Truth Set;
- saved experiment detail pages with aggregate metrics and per-question result summaries;
- saved experiment rename/delete actions and compact list metrics for questions, Hit, MRR, and Recall;
- categorized parameter sets with protected deletion;
- saved experiments that snapshot prepared data manifest hashes and parameter snapshots.

Start with these files:

1. `docs/PRODUCT_SPEC.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DOMAIN_MODEL.md`
4. `docs/API_CONTRACTS.md`
5. `docs/DEVELOPMENT_WORKFLOW.md`
6. `docs/DECISIONS.md`
7. `docs/DATA_POLICY.md`
