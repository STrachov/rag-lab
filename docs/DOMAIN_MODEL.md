# Domain Model

## Dataset

A named collection of documents.

Fields:

```text
dataset_id
name
description
domain
document_count
created_at
metadata
```

## Document

A source file or logical source item.

Fields:

```text
document_id
dataset_id
source_name
source_path
mime_type
text_hash
char_count
page_count
metadata
```

## Chunk

A retrievable text unit.

Fields:

```text
chunk_id
document_id
dataset_id
text
token_count
source_page
source_section
heading_path
start_char
end_char
metadata
```

## Configs

Core configs:

```text
ChunkingConfig
EmbeddingConfig
RetrievalConfig
PromptConfig
```

## EvalSet

A set of questions with expected sources and expected facts.

## Experiment

A reproducible run combining:

```text
dataset + eval_set + chunking + embedding + retrieval + prompt
```

## Traces

Required trace types:

```text
RetrievalTrace
AnswerTrace
```

## Recipe

A production-ready configuration created from a successful experiment.
