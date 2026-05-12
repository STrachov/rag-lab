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

---

## 2026-05-12 - Use editable data assets with manifest snapshots

Status: accepted

### Context

Data assets need practical file management: source upload, add/delete files, download by original filename, PDF inspection, and prepared versions. Saved experiments still need to remain tied to the data state used at creation time.

### Decision

- Data assets may be edited by adding and deleting files.
- Each file change creates a `DataAssetManifest` snapshot in PostgreSQL.
- `DataAsset.manifest_hash` points to the current manifest.
- `SavedExperiment.data_asset_manifest_hash` snapshots the prepared data manifest used by the experiment.
- Uploaded and generated files are stored under generated safe filenames; original filenames live in manifest JSON.
- Source assets can have linked prepared versions.
- Source asset deletion also deletes linked prepared versions, but assets used by saved experiments cannot be deleted.
- The first local preparation adapter is `pymupdf_text` for PDFs with text layers, `.txt`, and `.md`.

### Consequences

Pros:
- data management matches real experimentation workflows;
- manifest history is queryable and auditable in the application database;
- saved experiments remain tied to a specific data manifest;
- source files can be inspected before choosing a preparation path.

Cons:
- manifest snapshots are audit/history, not full file versioning after physical deletion;
- delete behavior must protect saved experiments;
- source/prepared relationships add UI complexity.
