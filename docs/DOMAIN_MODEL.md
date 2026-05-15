# Domain Model

## Project

A durable workspace for one RAG evaluation effort.

Fields:

```text
id
name
description
domain
status
metadata_json
created_at
updated_at
```

## DataAsset

A raw or prepared data reference inside a project.

Fields:

```text
id
project_id
name
asset_type: raw | prepared
data_format
storage_kind: uploaded | local_path | external_uri
parent_id
storage_path
manifest_hash
preparation_params_json
metadata_json
status
created_at
```

Prepared data is produced from source data by preparation parameters. PDF-to-Markdown, OCR, and document conversion settings belong in `preparation_params_json`.

Data assets may be edited by adding or deleting files. Each edit creates a new `DataAssetManifest` snapshot and updates `DataAsset.manifest_hash` to the current manifest hash.

`raw` assets are source data, not necessarily PDFs. They may be PDFs, Markdown, text, DOCX, HTML, or mixed files. Markdown is not automatically prepared data; a prepared asset is an explicitly RAG-ready version with preparation provenance.

`raw` assets should not have `parent_id`. `prepared` assets may reference a raw parent asset. Saved experiments should use prepared data assets and snapshot the current data asset manifest hash.

Uploaded files are stored under generated safe names. Original filenames are kept in manifest JSON.

Deleting an individual file removes the file from active storage but preserves prior manifest snapshots for that asset. Deleting a whole prepared asset removes its storage directory and its manifest snapshots. Deleting a source asset removes linked prepared versions first. Any data asset referenced by a saved experiment cannot be deleted.

## DataAssetManifest

A snapshot of a data asset's file manifest.

Fields:

```text
id
data_asset_id
manifest_hash
manifest_json
created_at
```

Manifest JSON includes generated storage paths, original filenames, content type, size, sha256 hash, optional file role/source links, and lightweight file inspection metadata for each current file.

PDF inspection should record page count, encryption status, document metadata, text layer signal, image counts, and scan likelihood. Inspection failures should not block upload; store failure details in the manifest entry.

Prepared data must include preparation provenance in `preparation_params_json`, for example:

```json
{
  "method": "external_gpu",
  "tool": "marker",
  "tool_version": "1.2.3",
  "source_format": "pdf",
  "output_format": "markdown",
  "command": "marker_single ...",
  "settings": {
    "ocr": true
  },
  "notes": "Parsed on a rented GPU server"
}
```

Built-in preparation requests carry method-specific `settings`; the saved `preparation_params_json` records normalized settings plus service provenance such as a Docling base URL.

The first preparation adapters are `pymupdf_text` and `docling`. `pymupdf_text` creates prepared Markdown from PDFs with extractable text layers and from plain text/Markdown source files. `docling` calls an external Docling Serve endpoint and stores both Markdown and full Docling JSON as prepared asset files.

## ParameterSet

A named reusable parameter bundle.

Fields:

```text
id
project_id
name
description
category
params_json
params_hash
created_at
```

Parameter sets use `category` to distinguish reusable presets:

```text
chunking
embedding
indexing
retrieval
reranking
generation
evaluation
general
```

Prepared data provenance is stored on `DataAsset.preparation_params_json`, not edited again from the
Chunking/Retrieval screens after preparation has already run. A saved experiment may still include preparation
provenance in its full parameter snapshot for reproducibility.

Chunking parameter sets use a backend-driven strategy catalog and canonical snapshot shape:

```json
{
  "chunking": {
    "strategy": "heading_recursive",
    "params": {
      "chunk_size": 900,
      "chunk_overlap": 120
    }
  }
}
```

Deleting a parameter set is allowed only while no saved experiment references it.

## GroundTruthSet

An optional set of expected facts, sources, labels, or judgments for evaluating saved experiments.
Ground truth files are project-scoped local files, not DataAsset records. A set may reference a
prepared data asset. For chunk-level qrels, compatibility with a specific chunks cache is checked
when retrieval/reranking evaluation runs, not when the ground truth set is created.

Fields:

```text
id
project_id
name
data_asset_id
storage_path
manifest_hash
metadata_json
created_at
```

For uploaded chunk-level qrels, `storage_path` points to
`data/ground_truth/{project_id}/ground_truths/{ground_truth_set_id}/ground_truth.json`.
`metadata_json` stores the canonical format, ground truth type, question and judgment counts,
declared chunk-file hash when available, and upload-time validation status such as `format_valid`.

## SavedExperiment

A persisted experiment record. Do not model a separate `ExperimentRun` as a main product concept.

Saved experiments snapshot the current prepared data manifest via `data_asset_manifest_hash` when they are created. Later edits to the data asset do not change existing experiment records.

Fields:

```text
id
project_id
name
data_asset_id
data_asset_manifest_hash
ground_truth_set_id
parameter_set_id
params_snapshot_json
params_hash
metrics_summary_json
status
notes
debug_level: none | summary | full
code_commit
pipeline_version
created_at
started_at
finished_at
error_json
```

## MetricValue

A single metric value attached to a saved experiment.

Fields:

```text
id
saved_experiment_id
metric_name
metric_value
metric_scope
created_at
```

## DerivedCache

Technical runtime/cache/debug outputs. This is not a product-facing result.

Fields:

```text
id
project_id
data_asset_id
params_hash
cache_type: chunks | embeddings | qdrant_index | retrieval_temp | answer_temp
cache_key
status
metadata_json
created_at
last_used_at
```

Current cache types:

```text
chunks
qdrant_index
retrieval_temp
answer_temp
```

`chunks` caches materialize prepared data into `raglab.chunks.v1` JSONL. Each chunk record uses stable project-native fields:

```text
chunk_id
source_name
stored_path
section
heading_path
page
token_count
char_count
text
```

Docling JSON files are not indexed as chunk text by default. They are preserved as prepared asset files and recorded as sidecar metadata on the chunk cache so later structure-aware chunking, tables, pages, or citation work can use a parser-independent shape.

`qdrant_index` caches store Qdrant collection references and index metadata. Current indexes use named dense vectors and, for sparse or hybrid indexes, local BM25-style sparse vectors. Metadata should include:

```text
collection_name
index_mode: dense | sparse | hybrid
embedding model snapshot
sparse model snapshot
sparse_stats_path
chunk_count
data_asset_manifest_hash
chunks_cache_id
```

Failed index attempts should be visible as `DerivedCache(status="failed")` with `metadata_json.error_json` instead of disappearing from the UI.

Reranking is currently a retrieval preview runtime step, not a separate cache type. It should be
run from a `retrieval_temp` cache that stores the query, retrieval mode, candidate count, index cache
reference, and retrieved candidate metadata. It should be represented in parameter snapshots through a
reranking model id, params, candidate count, and final top-k. Reranked traces also belong in
`retrieval_temp` if debug persistence is later expanded.

## Results

Results mean metrics only:

```text
quality metrics
retrieval metrics
citation metrics
latency/cost metrics
manual or LLM-judge scores
```
