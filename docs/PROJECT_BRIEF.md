# Project Brief

## Purpose

RAG Lab is a separate experimental project for testing RAG approaches before moving stable configurations into OCRlty main or client-specific deployments.

It answers questions such as:

- Which chunking strategy works best?
- Is dense retrieval enough, or do we need hybrid search?
- Is reranking worth the latency and cost?
- Are answers grounded in retrieved evidence?
- Can the system correctly say "not found"?
- Which settings should be used in production?

## What this project is

- RAG experiment workbench
- Retrieval debugging tool
- Evaluation harness
- Report generator
- Production recipe generator
- Upwork portfolio asset

## What this project is not

- Generic chatbot
- Full SaaS product
- Agent platform
- GraphRAG-first system

## Relationship to OCRlty main

```text
RAG Lab:
  experiments, metrics, traces, reports, recipes

OCRlty main:
  stable product features and production document workflows
```

Only validated recipes should move from RAG Lab to OCRlty main.
