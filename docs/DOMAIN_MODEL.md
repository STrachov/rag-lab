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

Manifest JSON includes generated storage paths, original filenames, content type, size, sha256 hash, and lightweight file inspection metadata for each current file.

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

The first local preparation adapter is `pymupdf_text`. It creates prepared Markdown from PDFs with extractable text layers and from plain text/Markdown source files.

## ParameterSet

A named reusable parameter bundle.

Fields:

```text
id
project_id
name
description
params_json
params_hash
created_at
```

Parameter sets may include:

```text
preparation
chunking
indexing
retrieval
reranking
generation
```

Preparation parameters include converter choice and settings, for example:

```text
pymupdf_text
docling
ocrmypdf_tesseract
marker
mineru
custom_vlm
```

## GroundTruthSet

An optional set of expected facts, sources, labels, or judgments for evaluating saved experiments.

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

## SavedExperiment

A persisted experiment record. Do not model a separate `ExperimentRun` as a main product concept.

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

## Results

Results mean metrics only:

```text
quality metrics
retrieval metrics
citation metrics
latency/cost metrics
manual or LLM-judge scores
```
