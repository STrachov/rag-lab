# Configs

## Purpose

Configs make experiments reproducible.

## Location

```text
configs/chunking/
configs/embedding/
configs/indexing/
configs/retrieval/
configs/reranking/
configs/prompts/
configs/eval/
```

## Preparation example

Preparation settings are part of the reproducibility surface. A prepared data asset stores its preparation metadata and every edit creates a manifest snapshot.

```yaml
config_id: pymupdf_text_default
method: pymupdf_text
tool: pymupdf
tool_version: ""
source_format: mixed
output_format: markdown
settings:
  page_breaks: true
notes: CPU text extraction for PDFs with extractable text layers, plus text and Markdown inputs.
```

Docling preparation example:

```yaml
config_id: docling_cpu_default
method: docling
tool: docling
source_format: mixed
output_format: markdown_json
output_formats:
  - markdown
  - json
settings:
  do_ocr: true
  force_ocr: false
  image_export_mode: placeholder
service:
  base_url: http://localhost:5001
  base_url_env: RAG_LAB_DOCLING_BASE_URL
notes: External Docling Serve conversion. Store Markdown and the full Docling JSON as prepared asset files.
```

## Chunking example

```yaml
config_id: heading_recursive_900_120
strategy: heading_recursive
params:
  chunk_size: 900
  chunk_overlap: 120
  tokenizer: cl100k_base
  preserve_headings: true
  preserve_tables: true
  page_boundary_mode: soft
```

Adapter-backed chunking example:

```yaml
config_id: langchain_recursive_character_1000_200
strategy: langchain_recursive_character
params:
  chunk_size: 1000
  chunk_overlap: 200
  separators: "\\n\\n|\\n| |"
  keep_separator: true
  is_separator_regex: false
```

Markdown-header adapter-backed chunking example:

```yaml
config_id: langchain_markdown_header_recursive_1000_200
strategy: langchain_markdown_header_recursive
params:
  headers_to_split_on: "#:h1|##:h2|###:h3|####:h4"
  strip_headers: false
  chunk_size: 1000
  chunk_overlap: 200
  separators: "\\n\\n|\\n| |"
  keep_separator: true
  is_separator_regex: false
```

## Embedding example

```yaml
config_id: intfloat_multilingual_e5_small_cpu
provider: sentence_transformers
model_id: intfloat_multilingual_e5_small
model_name: intfloat/multilingual-e5-small
dimensions: 384
device: cpu
normalize: true
query_prefix: "query: "
passage_prefix: "passage: "
```

```yaml
config_id: baai_bge_small_en_v1_5_cpu
provider: sentence_transformers
model_id: baai_bge_small_en_v1_5
model_name: BAAI/bge-small-en-v1.5
dimensions: 384
device: cpu
normalize: true
```

## Sparse retrieval example

```yaml
config_id: bm25_local_default
provider: rag_lab
model_id: bm25_local
params:
  lowercase: true
  min_token_len: 2
  k1: 1.2
  b: 0.75
```

## Qdrant index example

```yaml
config_id: qdrant_hybrid_e5_bm25
vector_store: qdrant
index_mode: hybrid
collection_name: ""
distance: Cosine
dense_vector_name: dense
sparse_vector_name: sparse
embedding:
  model_id: intfloat_multilingual_e5_small
  params:
    device: cpu
sparse:
  model_id: bm25_local
  params:
    lowercase: true
    min_token_len: 2
    k1: 1.2
    b: 0.75
```

## Retrieval example

```yaml
config_id: hybrid_rrf_top8
mode: hybrid
top_k: 8
fusion: rrf
rrf_k: 60
reranker:
  enabled: true
  candidate_k: 30
  model_id: qwen3_reranker_0_6b
```

## Reranking example

```yaml
config_id: qwen3_reranker_0_6b_cpu
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
