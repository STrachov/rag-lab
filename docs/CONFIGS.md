# Configs

## Purpose

Configs make experiments reproducible.

## Location

```text
configs/chunking/
configs/embedding/
configs/retrieval/
configs/prompts/
configs/eval/
```

## Chunking example

```yaml
config_id: heading_recursive_900_120
strategy: heading_recursive
chunk_size: 900
chunk_overlap: 120
tokenizer: cl100k_base
preserve_headings: true
preserve_tables: true
page_boundary_mode: soft
```

## Embedding example

```yaml
config_id: openai_text_embedding_3_small
provider: openai
model: text-embedding-3-small
dimensions: 1536
batch_size: 64
normalize: true
```

## Retrieval example

```yaml
config_id: hybrid_top8_rerank20
mode: hybrid
top_k: 8
score_threshold: 0.30
hybrid_alpha: 0.5
reranker:
  enabled: true
  rerank_top_n: 20
```

## Prompt config example

```yaml
config_id: grounded_answer_v1
template_path: configs/prompts/grounded_answer_v1.md
model: gpt-4.1-mini
temperature: 0
max_tokens: 900
citation_format: document_page_chunk
not_found_policy: strict
```
