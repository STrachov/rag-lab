# Artifacts And Derived Cache

## Purpose

Artifacts are technical files, manifests, and cache entries. They are not a product-facing concept.

Product-facing experiment results are metrics stored on saved experiments.

## Local Layout

```text
data/
  cache/
    chunks/
    embeddings/
    qdrant_indexes/
    retrieval_temp/
    answer_temp/
  manifests/
  ground_truth/
```

## Derived Cache

Derived cache may include:

```text
chunks
embeddings
qdrant_index
retrieval_temp
answer_temp
```

These outputs can be regenerated from:

```text
data asset reference
full parameter snapshot
code version
pipeline version
```

## Rules

- Do not treat artifacts as saved experiment results.
- Do not silently mutate cache files.
- Store hashes for manifests and parameter snapshots.
- Store prompts, traces, and generated answers only when debug mode requests them.
- Do not store secrets.
- Do not commit real client data or derived client cache.
