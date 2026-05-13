# RAG Lab

Experimental workbench for building, comparing, evaluating, and documenting RAG pipelines over project data.

The project is not a generic chat-with-PDF demo. Its purpose is to run controlled experiments inside durable project workspaces and export production-ready RAG recipes after metrics are understood.

Core flow:

```text
Project
-> Source Data Asset
-> Prepared Data Asset
-> Data Asset Manifest snapshot
-> categorized Parameter Set
-> optional Ground Truth Set
-> Saved Experiment
-> metrics comparison
-> validated recipe
```

In the UI, create or open a project first. The Data, Parameters, Ground Truth, Saved Experiments, and Comparison sections then operate inside that current project context.

Current implemented foundation:

- project-scoped source and prepared data assets with manifest snapshots;
- preparation through upload, `pymupdf_text`, or Docling Serve;
- backend-driven chunking strategy catalog;
- Chunking Lab with preview over prepared data assets;
- categorized parameter sets with protected deletion;
- saved experiments that snapshot prepared data manifest hashes and parameter snapshots.

Start with these files:

1. `docs/PROJECT_BRIEF.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DOMAIN_MODEL.md`
4. `docs/EXPERIMENTS.md`
5. `docs/EVALUATION.md`
6. `docs/UI_SPEC.md`
7. `docs/DEVELOPMENT_WORKFLOW.md`
