# Experiments

## Purpose

Experiments compare RAG configurations on a dataset and eval set.

## Required inputs

Every experiment must declare:

```text
dataset_id
eval_set_id
chunking_config_id
embedding_config_id
retrieval_config_id
prompt_config_id
```

## Required outputs

Every experiment should save:

```text
experiment_result.json
retrieval_traces.jsonl
answer_traces.jsonl
eval_report.json
failure_cases.csv
summary.md
```

## Baseline matrix

For each new dataset, run at least:

1. Full-context baseline if feasible.
2. Naive dense retrieval.
3. Hybrid retrieval.
4. Hybrid + reranking.
5. Strict not-found prompt.

## What to compare

```text
retrieval quality
citation quality
answer correctness
not-found behavior
latency
cost
failure cases
```

## Promotion rule

An experiment can be promoted to a recipe only if:

- metrics beat baseline;
- failure cases are understood;
- configs are explicit;
- prompt is versioned;
- citations are acceptable;
- not-found behavior was tested.
