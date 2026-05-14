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
    sparse/
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
Saving or deleting a ParameterSet changes only application state in PostgreSQL; it should not create,
mutate, or delete derived cache files.

Materialized chunk caches use `raglab.chunks.v1` JSONL with stable fields such as `chunk_id`,
`source_name`, `stored_path`, `heading_path`, token counts, character counts, and text. Parser-specific
outputs such as Docling JSON are preserved as sidecar metadata rather than becoming the internal
source of truth.

Sparse retrieval stats, such as local BM25 document frequencies and average document length, are
stored under `data/cache/sparse/` and referenced from the Qdrant index cache metadata.

Qdrant indexes are tracked as `DerivedCache(cache_type="qdrant_index")`. Current collections use
named vectors: `dense` for embedding vectors and `sparse` for BM25-style sparse vectors. Failed index
attempts should be tracked as `DerivedCache(status="failed")` with error metadata so the UI can show
what happened after navigation.

Retrieval preview may return clipped chunk text as `text_preview`, plus source metadata, dense or
sparse scores, and optional rerank scores. Reranking reads full materialized chunk text locally from
the chunks cache, but it does not add full text to Qdrant payloads. It is still debug output, not a
saved experiment result.

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
