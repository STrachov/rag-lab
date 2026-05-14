# Testing

## Purpose

Tests prevent silent regressions in the experiment engine.

## Unit tests

Use for:

```text
chunking
token counting
embedding model registry
sparse model registry
BM25 sparse vector building
Qdrant vector store adapter
hybrid retrieval fusion
reranker model registry
reranked retrieval ordering
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
chunk materialization -> Qdrant index cache -> retrieval preview
retrieval preview -> rerank candidates
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
embedding catalog or encoder behavior
sparse catalog or BM25 params
Qdrant collection/index behavior
retrieval preview payloads and score fields
reranking catalog and rerank score fields
failed derived cache records
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
-> materialize chunks
-> create Qdrant index
-> retrieve known answer with dense, sparse, or hybrid preview
-> rerank retrieved candidates
-> generate answer
-> evaluate hit@k
```
