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

## Projects

Show:

```text
id
name
domain
status
created_at
updated_at
```

Actions:

```text
create project
open project
archive project
```

## Data

Show raw and prepared data assets:

```text
id
name
asset_type
parent_id
storage_path
manifest_hash
preparation parameters
created_at
```

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
