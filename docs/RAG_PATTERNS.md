# RAG Patterns

## Full-context baseline

Use when the document set fits into model context. This is a required baseline when feasible.

## Naive dense-vector RAG

```text
chunk -> embed -> vector search -> answer
```

Use only as a baseline.

## Hybrid search

Dense vector search plus keyword/BM25 search.

Best for acronyms, legal references, product codes, exact terms, and accounting terminology.

Current RAG Lab hybrid retrieval uses Qdrant named vectors: `dense` for embeddings and `sparse` for a
local BM25-style sparse vector. Dense and sparse result lists are merged in the application layer with
reciprocal rank fusion for retrieval preview.

## Reranking

Retrieve many candidates, rerank, then pass the best chunks to the prompt.

Tradeoff: better quality, higher latency/cost.

Current RAG Lab reranking is a retrieval preview step over materialized chunk text. The first local
rerankers are `BAAI/bge-reranker-v2-m3`, `Qwen/Qwen3-Reranker-0.6B`, and
`cross-encoder/ms-marco-MiniLM-L6-v2`.

## Contextual chunks

Add document and section context to chunks before indexing.

Useful for legal, policy, audit, and technical documents.

## Parent-child retrieval

Retrieve small chunks, but pass a larger parent section to the answer prompt.

## Structured extraction instead of RAG

Use when the task asks for fixed fields:

```text
invoice fields
PO fields
bank statement transactions
form fields
report consistency checks
```

## GraphRAG

Advanced mode for global questions, entity relations, topic discovery, and cross-document summaries. Not part of the MVP.
