# Artifacts

## Purpose

Artifacts preserve experiment state, traces, reports, and recipes.

## Local layout

```text
data/artifacts/
  documents/
  chunks/
  indexes/
  retrieval_traces/
  answer_traces/
  experiments/
  eval_reports/
  reports/
  recipes/
```

## Required artifact types

### Document metadata

```json
{
  "document_id": "doc_001",
  "dataset_id": "dataset_001",
  "source_name": "contract.pdf",
  "mime_type": "application/pdf",
  "page_count": 12,
  "char_count": 42000,
  "text_hash": "sha256:..."
}
```

### Retrieval trace

```json
{
  "trace_id": "ret_001",
  "experiment_id": "exp_001",
  "question_id": "q_001",
  "retrieved_chunks": []
}
```

### Answer trace

```json
{
  "trace_id": "ans_001",
  "experiment_id": "exp_001",
  "prompt_template_id": "grounded_answer_v1",
  "prompt_hash": "sha256:...",
  "answer": "...",
  "citations": []
}
```

## Rules

- Do not silently mutate artifacts.
- Store config ids and config snapshots.
- Store prompt hashes.
- Do not store secrets.
- Do not commit real client artifacts.
