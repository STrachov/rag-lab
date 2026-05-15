# UI Specification

## Purpose

The UI is a project-oriented RAG experimentation workbench, not a generic chatbot.

## Left Menu

```text
Projects
Data
Chunking
Retrieval
Ground Truth
Saved Experiments
Comparison
Settings
```

## Current Project Context

The UI is organized around one current project.

Flow:

```text
create/open project
-> Data loads for current project
-> Chunking loads for current project
-> Retrieval loads derived chunk and Qdrant caches for current project
-> Ground Truth loads for current project
-> Saved Experiments load for current project
-> Comparison uses saved experiments from current project
```

The current project name and status should be visible near the top of the workbench or in the left menu. Sections that require a project should show an empty state when no project is selected instead of asking the user to choose a project again inside each section.

Project routes should keep the selected project in the address bar:

```text
/projects
/projects/{project_id}
/projects/{project_id}/data
/projects/{project_id}/chunking
/projects/{project_id}/retrieval
/projects/{project_id}/ground-truth
/projects/{project_id}/saved-experiments
/projects/{project_id}/comparison
/projects/{project_id}/settings
```

Opening `/projects/{project_id}` should redirect to `/projects/{project_id}/data`.

## Projects

Show:

```text
name
domain
description
updated_at
```

Technical fields such as `id` and `status` may exist in the API and database, but they should not be shown in the default project list unless needed for debugging or archive workflows.

Actions:

```text
create project
select project by clicking its name
archive project
```

## Data

Data is shown as source data rows with linked prepared versions, not as separate raw/prepared tables.

```text
Source Data
  files
  prepared versions
```

Source Data supports uploading source documents in formats such as PDF, Markdown, text, DOCX, HTML, or mixed. Prepared Versions support uploading Markdown or other prepared text outputs linked to a source data asset.

Adding source data and prepared versions should happen in modal dialogs. Preparation metadata should be entered as explicit fields, with advanced JSON reserved for later if needed.

Show data assets:

```text
name
asset_type
data_format
storage_kind
parent_id
manifest_hash
current manifest files
preparation parameters
status
created_at
```

Experiments should use prepared data assets. Raw/source data assets are source references.

Internal storage paths should not be shown as the primary file UI. Show original filenames as download links instead.

Deleting a source data asset should also delete its linked prepared versions after user confirmation. Assets used by saved experiments cannot be deleted.

File operations:

```text
add files to data asset
delete files from data asset
delete data asset, with confirmation
download file by original filename
create manifest snapshot after each change
store original filename in manifest
store file on disk under generated safe name
```

For PDFs, show lightweight inspection hints near each file:

```text
page count
text layer present or missing
likely scanned
encrypted
inspection failed
```

These hints help users choose a preparation path such as CPU text extraction, OCR, or external GPU parsing.

For source data, expose a compact `Prepare with` selector and a `Configure & Run` action rather than one button per converter. The selector should be populated from the backend preparation method catalog.

`Configure & Run` opens a modal for the selected method. The modal should show the prepared version name, read-only method/output/source manifest context, method-specific settings, and a read-only preview of the resulting preparation params.

Preparation methods should include converter choice and settings:

```text
pymupdf_text
docling
ocrmypdf_tesseract
marker
mineru
custom_vlm
```

Docling preparation should create a prepared version with Markdown and `*.docling.json` files. The JSON is preserved as a prepared data output for later context-building work; chunking is not required to consume it immediately.

Expose Docling `image_export_mode` values `placeholder` and `embedded`. Default to `placeholder` so Markdown remains compact and RAG-friendly. Do not expose Docling `referenced` until RAG Lab stores referenced image files as prepared asset files.

## Chunking

Show reusable parameter sets for:

```text
chunking
embedding
indexing
retrieval
reranking
generation
evaluation
```

Parameter set rows should show category/type, name, description, hash, created date, and available
actions. Categories distinguish chunking presets from embedding, indexing, retrieval, generation,
and evaluation presets. Parameter sets can be deleted unless they are referenced by a
saved experiment.

The Chunking workflow is a Chunking Lab:

```text
select prepared data asset
-> edit chunking parameters
-> preview chunk output
-> save reusable ParameterSet
```

Preparation settings are not edited here once a prepared data asset exists. They remain provenance
on the prepared data asset and may be included later in saved experiment snapshots as read-only
context.

Chunking preview should show:

```text
chunk count
files count
min/average/max token and character counts
chunks per source file
warnings
preview chunks with source file, page/section metadata, token count, and text preview
```

Preview chunks are derived debug output. They are not saved experiment results. Saved experiments
store the prepared data asset reference, data manifest hash, full parameter snapshot, parameter hash,
and metrics only.

Chunking strategies are backend-driven. The UI should load the strategy catalog from the API and
render the strategy selector plus simple parameter controls from the returned field metadata. A new
chunking strategy should be added by registering its id, label, default params, field metadata, and
chunking function in backend code.

The chunking workflow may offer a `Next` action that materializes the current chunking snapshot and
opens the Retrieval page with the resulting chunk cache selected.

The chunking workflow should also offer `Download GT authoring pack`. This action materializes the
current chunking snapshot if needed and downloads a zip containing prepared text, normalized chunks,
ground truth schema/template, and instructions for authoring `ground_truth.jsonl` outside the app.

## Retrieval

The Retrieval page is the first runtime workbench after chunking. It should support:

```text
select or materialize a chunks DerivedCache
load existing Qdrant index DerivedCache rows
show ready and failed index caches
select dense embedding model and params from the backend catalog
select sparse model and params from the backend catalog
choose index mode: dense, sparse, hybrid
create a Qdrant index cache
run retrieval preview against an index cache
store the retrieval candidate set as a retrieval_temp cache
rerank the current retrieval cache with a backend-driven reranker catalog
optionally select a ground truth set and question instead of typing a manual query
show compact retrieval and reranking metrics for the selected ground truth question
```

Existing indexes should remain visible after navigation because they are loaded from
`DerivedCache(cache_type="qdrant_index")`, not kept only in component state.

Failed index creation should be visible in the same list with the recorded error message. Runtime
errors should not silently disappear.

Retrieval and reranking should be separate UI actions. A user should be able to retrieve candidates
once, receive a `retrieval_cache_id`, and then rerun reranking with different models or params without
creating a new Qdrant retrieval.

Retrieval preview result cards should show:

```text
chunk_id
score
dense_score when available
sparse_score when available
rerank_score when available
original_score and original_rank when reranking is enabled
source filename
token count
chunk text preview
```

Embedding and sparse controls must be backend-driven. The UI should not hardcode model ids or sparse
parameter ranges. BM25-style `k1` and `b` are floats, so numeric inputs must support decimal steps.
Reranker controls must follow the same registry pattern and should support candidate count, device,
batch size, max length, score normalization, and model-specific fields such as Qwen instructions.

When a ground truth question is selected, the Retrieval page should fill the query from the selected
question and show compact ranking metrics after retrieval and reranking. The default UI should not
show expected/found/missing chunk lists; those may be added later as a debug/details view.

## Ground Truth

Show optional ground truth sets and their data asset references.

The Ground Truth page owns ground truth upload and file-shape validation. Uploads should accept a
JSON or JSONL file and an optional prepared data asset. Ground truth creation should not require a
chunks cache; chunk id compatibility belongs to retrieval/reranking evaluation, where the selected
GT set can be checked against the active chunks cache. The default table should show name,
validation status, question counts, links to the canonical and original files, and a separate delete
action. Technical identifiers and chunk-file hashes may be kept in details/debug views rather than
the default table. Deleting a ground truth set used by a saved experiment must be blocked. Retrieval and
reranking screens may select a ground truth set for live metrics, but they should not own ground
truth file management.

## Saved Experiments

Show:

```text
id
name
data_asset_id
data_asset_manifest_hash
ground_truth_set_id
parameter_set_id
params_hash
status
debug_level
created_at
metrics_summary_json
```

## Comparison

Compare saved experiments by metrics:

```text
retrieval metrics
citation metrics
quality metrics
latency/cost metrics
manual or LLM-judge scores
```

## Debug Views

Chunks, embeddings, Qdrant indexes, retrieval traces, prompts, and generated answers may appear in debug views later. They must be labeled as derived cache/debug outputs.
