# AGENTS.md

## Role of this repository

This repository is a RAG experimentation workbench. It is not a generic chatbot, not a LangChain demo.

The main goal is to test different RAG strategies on document datasets and export a production-ready recipe.

## Core rules for AI coding agents

- Prefer transparent, inspectable code over opaque framework chains.
- Use frameworks as adapters, not as the project domain model.
- Do not make LangChain `Document` or LlamaIndex `Node` the internal source of truth.
- Keep experiment results reproducible.
- Save traces for retrieval, answer generation, citations, and evaluation.
- Do not add GraphRAG, agents, or complex orchestration unless explicitly requested.
- Do not build a polished SaaS UI before the experiment workflow is stable.

## Preferred internal entities

Use project-native entities:

```text
Dataset
Document
Chunk
ChunkingConfig
EmbeddingConfig
RetrievalConfig
PromptConfig
EvalSet
Experiment
RetrievalTrace
AnswerTrace
ExperimentResult
Recipe
```

## Done criteria

A feature is not complete unless at least one is true:

- it has a test;
- it creates an inspectable artifact;
- it appears in an experiment result;
- it is documented in the relevant markdown file.

## Data safety

Never commit real client data, API keys, auth headers, private URLs, PII, PHI, financial data, or unredacted documents.
