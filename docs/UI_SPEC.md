# UI Specification

## Purpose

The UI is an engineering workbench, not a generic chatbot.

## First implementation

Use Streamlit first.

## Left menu

```text
Datasets
Chunk Explorer
Retrieval Playground
Answer Playground
Eval Sets
Experiment Comparison
Reports
Recipes
Settings
```

## Datasets

Show:

```text
dataset_id
name
domain
document_count
total characters/tokens
created_at
status
```

Actions:

```text
create dataset
upload documents
inspect documents
run indexing
delete local dataset
```

## Chunk Explorer

Show:

```text
document
chunking config
chunk text
token count
page
section
heading path
metadata
```

## Retrieval Playground

Show:

```text
question
retrieval config
top chunks
scores
source document/page/section
latency
```

## Answer Playground

Show:

```text
question
selected chunks
prompt template
prompt preview
model settings
answer
citations
latency/cost
```

## Experiment Comparison

Show:

```text
experiment id
chunking
retrieval
prompt
hit@k
MRR
citation precision
answer correctness
not-found accuracy
latency
cost
```

## Recipes

Show production-ready settings and allow YAML/JSON export.
