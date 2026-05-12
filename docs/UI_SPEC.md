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

For source data with a text layer or plain text inputs, expose a `Prepare with PyMuPDF` action that creates a prepared Markdown version linked to the source asset.

Preparation controls should include converter choice and settings:

```text
pymupdf_text
docling
ocrmypdf_tesseract
marker
mineru
custom_vlm
```

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
