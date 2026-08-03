# Product Spec

## Purpose

RAG Lab is a permanent project-oriented workbench for testing RAG strategies over durable project
data. It is not a generic chatbot, a LangChain demo, a document conversion product, or a
report-first system.

The product answers questions such as:

- Which data preparation method works best for this project's files?
- Which chunking, indexing, retrieval, reranking, generation, and evaluation parameters are worth
  keeping?
- Are answers grounded in retrieved evidence?
- Can the system correctly say "not found"?
- Which full parameter snapshot should become a production recipe?

## Core Workflow

Target end-to-end workflow:

```text
Create/open Project
-> Upload source Data Asset
-> Inspect source files
-> Prepare data with a registered preparation method
-> Save prepared Data Asset with preparation provenance
-> Tune chunking with registered strategy catalog
-> Materialize chunks as DerivedCache
-> Build dense, sparse, or hybrid Qdrant index cache
-> Run manual retrieval/reranking previews
-> Optionally use individual Ground Truth questions for live metrics
-> Save full experiment snapshot
-> Run evaluation over the selected Ground Truth Set
-> Compare metrics across Saved Experiments
-> Promote a validated recipe
```

The implemented boundary currently ends at saved-experiment comparison. Generation, citations, and
recipe promotion/export are planned. See `CURRENT_STATE.md` for the current implementation matrix.

Manual previews are for tuning and debugging. Product-facing experiment results are metrics only.
Chunks, embeddings, indexes, retrieval traces, prompts, generated answers, and authoring packs are
derived runtime/cache/debug outputs unless an explicit debug level requests persistence.

## Product Model

```text
Project
  Data
    source/raw data assets
    prepared data assets
    manifest snapshots
  Parameter Sets
    reusable stage presets, including preparation
  Ground Truth
    optional evaluation references
  Saved Experiments
    prepared data reference
    data manifest hash
    full parameter snapshot
    optional ground truth reference
    metrics only
```

Use `Data Asset`, not `Dataset`, as the product concept. Use `SavedExperiment`, not a separate
product-facing `ExperimentRun`. Reports may be derived later from saved experiment metrics, but they
are not a main concept yet.

## Stage Registries

User-facing stage choices must come from backend-owned catalogs or registries. The UI should render
selectors and controls from registry metadata instead of hardcoding method ids or parameter fields.

Current backend-driven catalogs/registries:

```text
preparation methods
chunking strategies
embedding models
sparse retrieval models
reranking models
```

Current indexing modes and retrieval strategies are validated backend contracts, but they are not
exposed as independent UI-field catalogs. Planned catalog families are:

```text
indexing options
retrieval modes and fusion settings
generation models/prompts
evaluation metrics/scorers
```

Generation models/prompts and evaluation metric catalogs are planned registry families; the current
implemented workflow is focused on preparation, chunking, indexing, retrieval, reranking,
ground-truth scoring/evaluation, and saved metrics.

Each registered implementation should declare:

```text
id
label
description
default params
field metadata for the UI
validation rules
implementation adapter/function
version/provenance where relevant
```

Frameworks such as LangChain, LlamaIndex, Haystack, Ragas, Qdrant, Docling, and local model
libraries may be used behind adapters. They must not become the internal source of truth.

## Data Preparation

Uploading files creates a raw/source `DataAsset`; it does not automatically create RAG-ready data.
After upload, the user chooses a preparation method and parameters. Preparation creates a prepared
`DataAsset` linked to the source asset.

Preparation methods should include:

```text
pymupdf_text
docling
ocrmypdf_tesseract
marker
mineru
custom_vlm
```

The first implemented methods are `pymupdf_text` and `docling`. `pymupdf_text` creates Markdown from
PDFs with extractable text layers plus text/Markdown files. `docling` calls Docling Serve and stores
both Markdown and full `*.docling.json` sidecars. Docling JSON is preserved for later structure-aware
work; it is not indexed as chunk text by default.

Docling preparation can also create parent-unit sidecars:

```text
*.pages.jsonl
*.chapters.jsonl
```

Page units represent page-level parent contexts. Chapter units represent section/chapter-level
parent contexts derived from Docling section headers. If a chapter exceeds `max_chapter_tokens`, the
chapter-level representation falls back to page units for that chapter so retrieval can still return
bounded parent contexts.

Preparation provenance belongs to the prepared data asset and is included in saved experiment
snapshots for reproducibility.

Canonical preparation snapshot:

```json
{
  "preparation": {
    "method_id": "docling",
    "tool": "docling",
    "tool_version": "",
    "source_format": "mixed",
    "output_format": "markdown_json",
    "params": {
      "do_ocr": true,
      "force_ocr": false,
      "image_export_mode": "placeholder",
      "extract_parent_units": true,
      "max_chapter_tokens": 2500
    },
    "service": {
      "base_url_env": "RAG_LAB_DOCLING_BASE_URL"
    }
  }
}
```

## Parameter Snapshots

Every experiment must be reproducible from:

```text
prepared data asset reference
prepared data manifest hash
full parameter snapshot
code commit
pipeline version
```

This is the required product invariant, not yet the complete behavior of UI-created experiments.
The current snapshot contains the index-cache id/key, retrieval settings, optional reranking settings,
and GT reference. Preparation, chunking, embedding, and sparse lineage is still resolved indirectly
through the referenced data asset and `DerivedCache` metadata, and `code_commit` is not populated by
the UI. The implementation must copy that lineage into the saved snapshot before the record can be
called independently reproducible after cache deletion.

The full snapshot may include:

```text
preparation
chunking
embedding
sparse
indexing
retrieval
reranking
generation
evaluation
```

Reusable `ParameterSet` records are category-scoped presets. `preparation` is a first-class
category: it describes the reusable intent for converting source data into RAG-ready data.
Applying a preparation ParameterSet to a source `DataAsset` creates a prepared `DataAsset`.

The prepared `DataAsset` stores an immutable applied snapshot in `preparation_params_json`, so it
remains reproducible even if the reusable ParameterSet is later renamed, changed, or deleted.

Parent-unit chunking strategies read prepared parent JSONL sidecars rather than raw Markdown:

```text
page_recursive -> *.pages.jsonl
chapter_recursive -> *.chapters.jsonl
```

They produce child chunks with `parent_id`, `parent_type`, page range, and parent text metadata.
Parent-aware retrieval strategies retrieve child chunks first, group them by parent id, aggregate
scores, and return full parent page or chapter contexts:

```text
parent_page_retrieval
parent_chapter_retrieval
```

LLM reranking is a separate implemented reranking catalog item, not part of the parent-retrieval
strategies. The current `openai_llm_reranker` scores candidates pointwise and can blend its relevance
score with the normalized retrieval score.

Target full snapshot example (generation/evaluation catalog fields shown here are still planned):

```json
{
  "preparation": {
    "method_id": "docling",
    "params": {
      "do_ocr": true,
      "image_export_mode": "placeholder"
    }
  },
  "chunking": {
    "strategy": "heading_recursive",
    "params": {
      "chunk_size": 900,
      "chunk_overlap": 120
    }
  },
  "parent_chunking": {
    "strategy": "page_recursive",
    "params": {
      "chunk_size": 300,
      "chunk_overlap": 50
    }
  },
  "indexing": {
    "index_mode": "hybrid",
    "embedding": {
      "model_id": "intfloat_multilingual_e5_small",
      "params": {
        "device": "cpu"
      }
    },
    "sparse": {
      "model_id": "bm25_local",
      "params": {
        "k1": 1.2,
        "b": 0.75
      }
    }
  },
  "retrieval": {
    "strategy": "parent_page_retrieval",
    "mode": "hybrid",
    "top_k": 8,
    "candidate_k": 30,
    "fusion": "rrf",
    "rrf_k": 60,
    "parent_score": "max"
  },
  "reranking": {
    "enabled": true,
    "model_id": "qwen3_reranker_0_6b",
    "params": {
      "device": "cpu",
      "batch_size": 8,
      "max_length": 512,
      "normalize_scores": true
    }
  },
  "generation": {
    "prompt_template_id": "grounded_answer_v1",
    "model": "gpt-4.1-mini",
    "temperature": 0,
    "not_found_policy": "strict"
  },
  "evaluation": {
    "metrics": [
      "hit@k",
      "mrr",
      "answer_correctness",
      "citation_precision",
      "not_found_accuracy"
    ]
  }
}
```

## Ground Truth And Evaluation

Ground truth sets are optional project-scoped files. They may reference a prepared data asset.
Chunk-id compatibility is checked when evaluation runs against a selected chunks cache, not when the
ground truth file is uploaded.

Question shape:

```json
{
  "question_id": "q_001",
  "question": "What are the payment terms?",
  "answer_type": "factual",
  "expected_sources": [
    {
      "source_name": "contract.pdf",
      "page": 4,
      "section": "Payment Terms"
    }
  ],
  "expected_facts": [
    "Payment is due within 30 days"
  ]
}
```

Answer types:

```text
factual
multi_hop
comparison
definition
table_lookup
negative_not_found
summary
policy_interpretation
```

Manual retrieval/reranking previews may use one selected ground truth question and show compact
metrics. The current saved-experiment evaluation runs synchronously over all selected ground truth
questions, optionally reranks candidates according to the saved snapshot, and writes aggregate and
per-question summaries to `SavedExperiment.metrics_summary_json`.

Currently emitted retrieval metrics:

```text
chunk-level: hit@k, MRR@k, nDCG@k, precision@k, recall@k
page-level: page_hit@k, page_MRR@k, page_precision@k, page_recall@k
not-found: expected_not_found, returned_count, top_score
operational for remote reranking: requests, retries, candidates, tokens, duration, estimated cost
```

Target metric families:

```text
retrieval: hit@k, MRR, recall@k, nDCG@k, source_recall, source_precision
page-oriented retrieval: page_hit@k, page_MRR, page_recall@k
answer: answer_correctness, groundedness, citation_precision, citation_recall, not_found_accuracy
operational: latency_ms, models, candidate_k, token counts, estimated_cost
```

Failure categories should be inspectable in summaries or debug views:

```text
source_not_retrieved
wrong_source_retrieved
correct_source_low_rank
answer_unsupported
answer_incomplete
citation_wrong
not_found_failed
table_parsing_failed
chunk_boundary_problem
metadata_filter_problem
```

## UI Workbench

The UI is organized around one current project:

```text
Project
  Projects
  Data
  Ground Truth
Pipeline
  Preparation
  Chunking
  Retrieval
Evaluation
  Saved Experiments
Admin
  Settings (placeholder; environment-backed runtime configuration only)
```

The Projects page supports editing project name, domain, description, and lifecycle status. Projects
may be `active` or `archived`; archived projects remain durable and openable. The project list can be
filtered to active projects while retaining an all-projects view for restoring archived work.

The Data page owns source/prepared asset inventory, upload, file inspection, download, and deletion.
The Preparation page owns registered preparation methods, parameter editing, preparation
ParameterSet creation, and materializing prepared data assets. Preparation should not be hidden in a
modal inside Data.

Pipeline pages should share a consistent workbench shape. The left column contains input selection,
registered strategy controls, reusable ParameterSets, materialized outputs, and safe delete actions.
The right column contains preview/details panels and the current JSON snapshot. Preparation follows
this pattern with source selection, saved preparation ParameterSets, prepared output selection, source
manifest details, applied preparation snapshot, and generated file details.

The Chunking page previews registered chunking strategies with full text for returned preview chunks
and can materialize chunk caches. The Retrieval page builds and reuses Qdrant index caches, previews
retrieval, reranks saved candidate sets, and can launch full GT evaluation for the selected index.
The Ground Truth page owns upload and validation. Saved Experiments owns full snapshots,
rename/delete actions, compact list metrics such as question count, Hit, MRR, and Recall, detail
pages with per-question GT/retrieved summaries, evaluation status, metrics, errors, and comparison.
Comparison is an inline derived Saved Experiments view, not a separate domain entity: selected saved
experiments become columns, and the first comparison view lists question count, Hit, MRR, Recall,
operational summaries, and each experiment's submitted parameter snapshot. Until the known snapshot
lineage gap is closed, that submitted JSON is not independently self-contained.

## Citations And Generation

Generated factual answers must cite retrieved evidence. If evidence is insufficient, the generation
stage should return not-found according to the selected policy.

Minimum citation fields:

```text
chunk_id
document_id
source_name
```

Recommended fields:

```text
page
section
heading_path
score
rerank_score
text_span
```

Prompt templates are versioned configuration. Do not edit important prompt templates in place; create
new versions such as `grounded_answer_v2.md`.

## Recipe Output

Recipe promotion/export is a planned capability; no recipe entity, status API, or export workflow is
implemented yet.

A recipe is the production-ready output of RAG Lab. It is promoted only after metrics beat baseline,
failure cases are understood, preparation and retrieval parameters are explicit, prompts are
versioned, citations are acceptable, and not-found behavior was tested.

Recipe statuses:

```text
draft
recommended
accepted
deprecated
```

## Roadmap

```text
Completed
1. Project, data asset, manifest, parameter set, and saved experiment foundation
2. Data upload, inspection, and preparation registry
3. Chunking, materialized chunks, Qdrant indexing, retrieval, and reranking previews
4. Saved-experiment GT evaluation and inline comparison

Next
5. Make saved experiment snapshots self-contained and populate code provenance
6. Add background evaluation execution and progress/cancellation
7. Add generation, citations, versioned prompts, and not-found behavior
8. Add recipe promotion/export after generation and evaluation metrics are stable
```
