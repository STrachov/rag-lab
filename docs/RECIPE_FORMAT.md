# Recipe Format

## Purpose

A recipe is the production-ready output of RAG Lab.

## YAML example

```yaml
recipe_id: client_policy_rag_v1
name: Client policy document RAG v1
status: recommended

recommended_for:
  - policy lookup
  - factual Q&A
  - source-cited answers

not_recommended_for:
  - invoice field extraction
  - handwritten scans
  - table-heavy extraction

chunking:
  strategy: heading_recursive
  params:
    chunk_size: 900
    chunk_overlap: 120
    preserve_headings: true
    preserve_tables: true

embedding:
  provider: sentence_transformers
  model_id: intfloat_multilingual_e5_small
  model_name: intfloat/multilingual-e5-small
  dimensions: 384
  device: cpu
  normalize: true

sparse:
  provider: rag_lab
  model_id: bm25_local
  params:
    lowercase: true
    min_token_len: 2
    k1: 1.2
    b: 0.75

vector_store:
  backend: qdrant
  index_mode: hybrid
  distance: cosine
  dense_vector_name: dense
  sparse_vector_name: sparse

retrieval:
  mode: hybrid
  top_k: 8
  candidate_k: 30
  fusion: rrf
  rrf_k: 60

reranking:
  enabled: true
  provider: sentence_transformers
  backend: cross_encoder
  model_id: qwen3_reranker_0_6b
  model_name: Qwen/Qwen3-Reranker-0.6B
  params:
    device: cpu
    batch_size: 8
    max_length: 512
    normalize_scores: true
    instruction: Given a web search query, retrieve relevant passages that answer the query

generation:
  model: gpt-4.1-mini
  temperature: 0
  prompt_template_id: grounded_answer_v1
  not_found_policy: strict

eval_summary:
  hit_at_5: 0.86
  mrr: 0.74
  citation_precision: 0.79
  not_found_accuracy: 0.90
```

## Statuses

```text
draft
recommended
accepted
deprecated
```
