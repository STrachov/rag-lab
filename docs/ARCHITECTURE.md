# Architecture

## High-level flow

```text
documents
→ loaders
→ normalized documents
→ chunkers
→ chunks + metadata
→ embeddings
→ vector store
→ retrieval
→ optional reranking
→ prompt rendering
→ answer generation
→ citations
→ evaluation
→ report + recipe
```

## Recommended structure

```text
app/
  api/
  models/
  services/
  adapters/
  core/
ui/
configs/
  chunking/
  embedding/
  retrieval/
  prompts/
  eval/
data/
  datasets/
  artifacts/
  experiments/
  reports/
  recipes/
tests/
infra/
```

## Backend

Use Python + FastAPI.

Responsibilities:

- manage datasets;
- ingest documents;
- chunk documents;
- build indexes;
- run retrieval;
- generate answers;
- evaluate results;
- save artifacts;
- export reports and recipes.

## UI

Use React/Vite.

The UI must focus on analysis: chunks, retrieval, traces, eval, reports. Chat is only one screen, not the whole product.

## Adapters
External services must be wrapped:

```text
Embedder
VectorStore
Loader
Reranker
LLM
Evaluator
```

This keeps Qdrant, OpenAI, local models, LlamaIndex, LangChain, Haystack, or Ragas replaceable.
