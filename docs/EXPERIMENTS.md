# Experiments

## Purpose

Saved experiments compare parameter snapshots against data assets, usually with a ground truth set.

## Required Inputs

Every saved experiment must declare:

```text
project_id
data_asset_id
data_asset_manifest_hash
params_snapshot_json
params_hash
```

Optional references:

```text
ground_truth_set_id
parameter_set_id
```

`data_asset_manifest_hash` is captured from the prepared data asset at saved experiment creation time. This keeps experiment records tied to the exact data manifest used even if the data asset is edited later.

## Parameter Snapshot

The saved experiment stores the full parameter snapshot used at execution time. It may include:

```text
preparation
chunking
embedding
indexing
retrieval
reranking
generation
evaluation
```

Preparation includes PDF-to-Markdown, OCR, or document conversion method and settings.

Indexing, retrieval, and reranking snapshots should include the embedding model, sparse model, Qdrant
collection settings, index mode, retrieval mode, candidate count, reranker model, reranker params, and
fusion settings used for the run.

## Results

Saved experiment results are metrics only.

Examples:

```text
hit@k
MRR
source_recall
citation_precision
answer_correctness
not_found_accuracy
latency_ms
estimated_cost
manual_score
llm_judge_score
```

## Derived Runtime Outputs

Chunks, embeddings, sparse stats, Qdrant indexes, retrieval traces, prompts, and generated answers are derived cache/debug outputs. They should not be persisted as core results unless the saved experiment uses an explicit debug level:

```text
none
summary
full
```

Current derived runtime outputs include materialized chunk JSONL, local BM25 stats, Qdrant indexes
with named dense/sparse vectors, retrieval previews with clipped chunk text, and optional reranked
candidate traces.

## Baseline Matrix

For each new project and data asset, compare at least:

1. Full-context baseline if feasible.
2. Naive dense retrieval.
3. Sparse BM25-style retrieval.
4. Hybrid retrieval.
5. Hybrid + reranking.
6. Strict not-found generation parameters.

## Promotion Rule

A parameter snapshot can be promoted toward a recipe only if:

- metrics beat baseline;
- failure cases are understood;
- preparation and retrieval parameters are explicit;
- prompts are versioned;
- citation metrics are acceptable;
- not-found behavior was tested.
