# UI Specification

## Purpose

The UI is a project-oriented RAG experimentation workbench, not a generic chatbot.

## Left Menu

```text
Projects
Data
Parameters
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
-> Parameters load for current project
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
/projects/{project_id}/parameters
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

## Parameters

Show reusable parameter sets for:

```text
preparation
chunking
indexing
retrieval
reranking
generation
evaluation
```

Parameter set rows should show category/type, name, description, hash, created date, and available
actions. Categories distinguish chunking presets from future embedding, indexing, retrieval,
generation, and evaluation presets. Parameter sets can be deleted unless they are referenced by a
saved experiment.

The first implemented Parameters workflow is a Chunking Lab:

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

## Ground Truth

Show optional ground truth sets and their data asset references.

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
