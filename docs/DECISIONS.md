# Decisions

## Template

```markdown
## YYYY-MM-DD — Decision title

Status: proposed / accepted / deprecated

### Context

What problem are we solving?

### Decision

What did we decide?

### Alternatives considered

- Option A
- Option B

### Consequences

What becomes easier?
What becomes harder?
What should be revisited later?
```

---

## 2026-05-10 — Build RAG as a separate lab project

Status: accepted

### Context

OCRlty main is already a stable product-oriented document intelligence system. RAG work requires frequent experiments with chunking, retrieval, indexing, prompts, and eval.

### Decision

Create OCRlty RAG Lab as a separate experimental project. Move only validated recipes into OCRlty main.

### Consequences

Pros:
- experimentation does not overload OCRlty main;
- cleaner portfolio asset;
- easier client-specific testing.

Cons:
- some duplicated infrastructure at the start;
- later integration bridge may be needed.

---

## 2026-05-10 — Use frameworks as adapters

Status: accepted

### Context

LangChain, LlamaIndex, Haystack, and Ragas are useful, but they can make traces and experiment control opaque.

### Decision

Use project-native models for core entities. Use frameworks only as adapters.

### Consequences

Pros:
- clearer debugging;
- easier recipe export;
- less framework lock-in.

Cons:
- more initial code to write manually.

---

## 2026-05-11 â€” Use project-oriented model with metrics-only results

Status: accepted

### Context

The platform needs to be a permanent project-oriented RAG experimentation and evaluation system, not a dataset-first prototype or report generator.

### Decision

- The platform is organized around Project -> Data -> Parameters -> Ground Truth -> Saved Experiments.
- Results are metrics only.
- Chunks, indexes, embeddings, traces, prompts, and generated answers are derived cache/debug outputs.
- Data preparation, including PDF-to-Markdown conversion method, is part of the parameter snapshot.

### Alternatives considered

- Use datasets as the top-level product concept.
- Store traces and generated answers as core experiment results.
- Make reports a first-class product model immediately.

### Consequences

Pros:
- clearer product model;
- easier comparison across saved experiments;
- less accidental persistence of sensitive derived data;
- conversion choices are reproducible.

Cons:
- debug output needs explicit opt-in;
- reporting will be derived later instead of being modeled now.
