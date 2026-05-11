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
  chunk_size: 900
  chunk_overlap: 120
  preserve_headings: true
  preserve_tables: true

embedding:
  provider: openai
  model: text-embedding-3-small
  dimensions: 1536

vector_store:
  backend: qdrant
  distance: cosine

retrieval:
  mode: hybrid
  top_k: 8
  score_threshold: 0.30
  reranker:
    enabled: true
    rerank_top_n: 20

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
