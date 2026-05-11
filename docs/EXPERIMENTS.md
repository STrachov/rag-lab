# Experiments

## Purpose

Saved experiments compare parameter snapshots against data assets, usually with a ground truth set.

## Required Inputs

Every saved experiment must declare:

```text
project_id
data_asset_id
params_snapshot_json
params_hash
```

Optional references:

```text
ground_truth_set_id
parameter_set_id
```

## Parameter Snapshot

The saved experiment stores the full parameter snapshot used at execution time. It may include:

```text
preparation
chunking
indexing
retrieval
reranking
generation
evaluation
```

Preparation includes PDF-to-Markdown, OCR, or document conversion method and settings.

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

Chunks, embeddings, Qdrant indexes, retrieval traces, prompts, and generated answers are derived cache/debug outputs. They should not be persisted as core results unless the saved experiment uses an explicit debug level:

```text
none
summary
full
```

## Baseline Matrix

For each new project and data asset, compare at least:

1. Full-context baseline if feasible.
2. Naive dense retrieval.
3. Hybrid retrieval.
4. Hybrid + reranking.
5. Strict not-found generation parameters.

## Promotion Rule

A parameter snapshot can be promoted toward a recipe only if:

- metrics beat baseline;
- failure cases are understood;
- preparation and retrieval parameters are explicit;
- prompts are versioned;
- citation metrics are acceptable;
- not-found behavior was tested.
