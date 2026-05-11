# Testing

## Purpose

Tests prevent silent regressions in the experiment engine.

## Unit tests

Use for:

```text
chunking
token counting
citation building
eval metrics
config loading
recipe export
prompt rendering
```

## Integration tests

Use for:

```text
document ingest → chunk → index → retrieve
retrieve → answer trace
experiment run → eval report
recipe promotion
```

## Golden tests

Use fixed synthetic documents and expected outputs.

Examples:

```text
expected chunks for a markdown document
expected source found for a known question
expected not-found result for absent evidence
```

## Required tests

Add tests when changing:

```text
chunkers
retrievers
rerankers
citation builder
eval metrics
prompt renderer
recipe exporter
artifact writers
```

## Smoke test

```text
synthetic dataset
→ chunk
→ index
→ retrieve known answer
→ generate answer
→ evaluate hit@k
```
