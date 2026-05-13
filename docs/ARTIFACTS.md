# Artifacts And Derived Cache

## Purpose

Artifacts are technical files, generated storage filenames, and cache entries. They are not a product-facing concept.

Product-facing experiment results are metrics stored on saved experiments.

Data asset manifest snapshots are application state stored in PostgreSQL, not just loose files on disk. A current `_manifest.json` may be written next to files for inspection/export convenience, but `data_asset_manifests.manifest_json` is the authoritative manifest history.

## Local Layout

```text
data/
  projects/
    {project_id}/
      source/
        {data_asset_id}/
          files/
          _manifest.json
      prepared/
        {data_asset_id}/
          files/
          _manifest.json
  cache/
    chunks/
    embeddings/
    qdrant_indexes/
    retrieval_temp/
    answer_temp/
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

Chunking preview in the Parameters section is a computed API response by default. It may show chunk
text previews and chunk statistics, but it does not create a product-facing result. When chunking is
needed for an experiment or a later runtime step, the same prepared data manifest and chunking
parameter hash may be materialized under `data/cache/chunks/` and tracked through `DerivedCache`.

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
- Store data asset manifest snapshots in the application database.
- Store uploaded/generated files under safe generated filenames; keep original filenames in manifest JSON.
- Saved experiments must snapshot the prepared data asset manifest hash used for the run.
- Store prompts, traces, and generated answers only when debug mode requests them.
- Do not store secrets.
- Do not commit real client data or derived client cache.
