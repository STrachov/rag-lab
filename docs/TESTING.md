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
file inspection
preparation adapters
```

## Integration tests

Use for:

```text
source upload -> inspection -> prepared version
document ingest -> chunk -> index -> retrieve
retrieve -> answer trace
experiment run -> saved metrics
recipe promotion
```

## Golden tests

Use fixed synthetic documents and expected outputs.

Examples:

```text
expected PDF inspection for a synthetic text-layer PDF
expected prepared Markdown for a source document
expected chunks for a markdown document
expected source found for a known question
expected not-found result for absent evidence
```

## Required tests

Add tests when changing:

```text
data asset upload/delete/download
parameter set category/create/delete protections
file inspection
preparation adapters
chunking strategy catalog and preview
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
synthetic source data
-> prepare markdown
-> chunk
-> index
-> retrieve known answer
-> generate answer
-> evaluate hit@k
```
