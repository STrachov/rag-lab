# SavedExperiment reproducibility

One SavedExperiment is one backend-generated immutable pipeline snapshot and one evaluation attempt.
There are no evaluation-history entities or legacy snapshot readers. Development experiments,
GroundTruthSets and runtime caches created before this contract must be recreated.

## Create contract

`POST /v1/projects/{project_id}/saved-experiments` accepts choices only:

```json
{
  "name": "Wheeler 300/50",
  "index_cache_id": "selected-ready-index-id",
  "ground_truth_set_id": "selected-verified-gt-id",
  "retrieval": {
    "strategy": "chunk_retrieval",
    "mode": "hybrid",
    "top_k": 5,
    "candidate_k": 30,
    "parent_score": "max"
  },
  "reranking": null,
  "notes": null,
  "parameter_set_id": null,
  "debug_level": "summary"
}
```

Enabled reranking accepts `enabled`, `model_id` and `params`. The backend resolves concrete model,
provider/backend, normalized params, text-input policy and pricing assumptions. Defaults are resolved
at creation, not acquired from future catalogs during evaluation. Extra create fields are rejected,
including `params_snapshot_json`, `params_hash`, data/manifest claims, results and `code_commit`.

Creation requires a ready project Qdrant index and ready chunks cache with verified content metadata.
It checks actual chunks bytes against the materialization hash and against the index's build-time
`input_chunks_sha256`. Sparse/hybrid indexes also require verified BM25 statistics. Missing metadata,
files, historical manifests or inconsistent lineage produce an explicit HTTP 400; rebuild/re-import
instead of certifying an old output.

Historical lineage is resolved from the selected index:

```text
qdrant_index DerivedCache
  -> chunks DerivedCache
  -> DataAssetManifest identified by chunks.data_asset_manifest_hash
  -> preparation_params_json + parent_id from that historical manifest
  -> source DataAssetManifest identified by preparation.source_manifest_hash
```

The current prepared/source DataAsset manifest is not used to describe an old index. If the index
used M1 and the asset now points to M2, the experiment records M1. Externally prepared uploads need
source lineage in their applied preparation provenance to be used in this workflow.

## Stored snapshot

`params_snapshot_json.schema_version` is `raglab.saved_experiment.v1`. There is one schema:

| Section | Stored values |
| --- | --- |
| `data.source`, `data.prepared` | Asset ID, historical manifest ID/hash and ordered compact file entries: paths, names, sizes, SHA-256, roles/source links/content types where present |
| `data.preparation` | Applied preparation provenance copied from the historical prepared manifest, including source-manifest hash and actual conversion settings |
| `chunking` | Strategy, normalized params, effective size unit, cache ID/key, `chunks_file_sha256`, chunk count |
| `embedding` | Provider, model ID, concrete model, params, vector size and query/passage prefixes |
| `sparse` | Null or sparse model/params, statistics schema and `stats_file_sha256` |
| `index` | Cache ID/key, physical collection name, mode/distance, recipe `params_hash`, `input_chunks_sha256` |
| `retrieval` | Strategy/mode, top-k, requested candidate-k, effective candidate-k, parent aggregation/restoration, fusion and RRF constant |
| `reranking` | Null or resolved enabled/provider/backend/model/params/text-input configuration |
| `ground_truth` | GT ID, manifest hash, `canonical_sha256`, canonical/type/annotation versions, question count and declared slice definitions |
| `semantics` | `retrieval_version: raglab.retrieval.v1`, `evaluation_version: raglab.gt_eval.v1` |

No source/prepared/chunk text, vectors, BM25 vocabulary or retrieved traces are stored in this
snapshot. Results retain the existing aggregate and compact per-question/slice metric structure.

## Verified production inputs

Preparation reads each selected source input once as bytes and verifies its SHA-256 against
its source manifest entry. PyMuPDF opens the verified PDF buffer, text conversion decodes the
verified buffer, and Docling receives base64 of that same buffer. Missing or mismatched inputs fail
before conversion; the path is never reopened for processing.

Materialization resolves the manifest matching the selected prepared asset's manifest hash.
Only input files selected by the chunking strategy are required: Markdown/text or the selected
page/chapter JSONL roles. Each required input is read once, verified against its manifest entry,
and decoded from that same buffer. Missing inputs and hash mismatches fail without creating a
ready chunks cache. Unused sidecars are not required. Existing universal-newline decoding behavior
is preserved. These checks do not retain files or redesign storage.

Embedding numeric catalog bounds are validated before snapshot/hash creation. Voyage executes
the saved batch size without a second runtime clamp. A reranker backend that rejects the saved
prompt configuration fails explicitly; initialization never retries with the prompt removed.

## Hash meanings

- File SHA-256 identifies bytes. Source/prepared manifest hashes retain their existing manifest-JSON
  meaning and identify historical file inventories; they are not hashes of concatenated documents.
- Chunks materialization writes explicit UTF-8 bytes and stores their exact SHA-256 in
  `DerivedCache.metadata_json.chunks_file_sha256`, plus `chunk_count` and effective `size_unit`.
- Indexing reads/verifies that byte buffer before parsing it and stores its hash as
  `input_chunks_sha256`. This must equal the experiment's `chunking.chunks_file_sha256`.
- Sparse index metadata stores `sparse_stats_sha256` over exact persisted statistics bytes; the
  experiment copies it as `sparse.stats_file_sha256`.
- GT upload serializes canonical JSON to explicit UTF-8 bytes. `canonical_sha256` is stored in its
  manifest and metadata and copied to the experiment. The existing GT manifest hash remains a hash
  of the manifest, now including that new field. It is not renamed or repurposed.
- SavedExperiment `params_hash` hashes normalized effective parameter configuration only: preparation
  configuration, chunking, embedding, sparse config, index mode/distance, effective retrieval,
  reranking, GT scoring type and semantics versions. It excludes IDs, file/content hashes, file
  inventories, code, metrics and GT question/slice population. Requested candidate-k is excluded
  because effective candidate-k is the executed configuration. This is not a whole-snapshot hash.
- Qdrant `params_hash` retains the index-recipe meaning (including input chunks cache key and
  requested collection name). It is not a vector-content hash. IDs/keys are locators, not content
  proofs; different builds may have the same recipe hash but have distinct cache IDs/keys/collections.

New chunk materializations use distinct locations. Index builds use a physical collection named
from their fresh cache/build ID, independently of the requested logical name. Ready builds are never
upserted by another build. Existing physical collections are rejected by the creation adapter.
Deleting a cache does not make its old physical collection eligible for reuse. This isolation is
guaranteed by application build paths; it does not prevent arbitrary external Qdrant modifications.
Evaluation uses the currently configured Qdrant server; URL snapshotting is outside this contract.

## Evaluation attempt

`POST /v1/projects/{project_id}/saved-experiments/{id}/evaluate` takes no choices; an empty JSON body
is allowed. An `index_cache_id` in this body is rejected. Evaluation always uses `snapshot.index.cache_id`.

A conditional database update atomically claims `created -> running`. Every other status returns
HTTP 409 without changing metrics, timestamps or provenance. After a claim, missing inputs and
initialization errors consume the attempt and record `failed`; per-question failures retain the
existing `completed_with_errors` behavior. Retrying requires a new SavedExperiment.

Before scoring, the backend reads canonical GT bytes once, verifies the saved hash, parses/validates
once, and uses that same canonical object for questions, qrels, metadata, annotations and slices.
Chunks and required sparse statistics are read/verified once and reused from memory. No per-question
GT/file reload occurs. A declared GT chunks hash mismatch is an explicit failure. Required full chunk
reranking text cannot silently fall back to a preview.

Snapshot-resolved model descriptors instantiate the execution adapters without consulting current
model catalogs. Ready index identity/configuration must still match the saved binding. Required local
file deletion/mutation after loading cannot change the running evaluation's captured inputs.

## Effective behavior and versions

Effective candidates are `min(100, max(top_k, candidate_k or default))`, where the default is
`top_k * 5` for hybrid and `top_k` otherwise. Hybrid uses RRF with constant 60. Those effective values
are saved. Native chunkers use approximate whitespace tokens; LangChain character splitters use
characters. The tokenizer label does not change the native counting algorithm.

Parent retrieval behavior is unchanged: restore parent text from chunks and clip the returned parent
preview to 1,200 characters; parent reranking uses that preview. This policy is explicitly saved.
Page scoring remains single-document page-index matching; no document-aware matching was added.
Failed questions are excluded from metric averages, and each metric records its own contributing
question count. Overall and declared slices share that aggregation path.

Increment constants in `app/services/semantics.py` when retrieval/fusion, scoring or aggregation
behavior changes comparability. Unsupported saved semantics are rejected, not silently reinterpreted.

## Execution code

The backend captures best-effort execution code provenance into the existing `code_commit`
column, using `RAG_LAB_CODE_COMMIT` first, bounded Git SHA detection second, or null otherwise.
`metrics_summary_json.evaluation.code` stores `commit`, `commit_source` (`environment`, `git`,
`unavailable`) and `dirty` (true/false/null). Environment-supplied revisions have unknown dirty state.
Git absence cannot prevent evaluation. Provenance is retained on failed attempts too. The backend
sets `pipeline_version`; creation does not claim to know the future evaluation's code commit.

Environment/Git provenance is not proof of the code already loaded by a running process after
checkout changes. No package fingerprints, producer commits or model/vector-weight hashes are captured
by this task.

## Controlled series and storage boundary

Detail shows compact provenance; Compare highlights differing controls alongside existing metrics and
slices. Wheeler comparisons should hold historical data, preparation, embedding/sparse configuration,
canonical GT, retrieval/reranking, semantics and execution code fixed while varying chunk size/overlap.
Use page-level judgments for a common GT across chunk layouts; chunk IDs belong to their materialization.

No database migration is required. Remove/recreate old development SavedExperiments and derived
caches; re-import GT to produce canonical hashes. This change does not delete existing local data.

Saved snapshots and completed metrics remain inspectable after cache deletion. An unevaluated record
with missing required caches/files fails explicitly. Hashes do not retain deleted files: source/prepared
retention protection, content-addressed storage and cross-machine replay/transport remain out of scope.

## Implementation files and verification

Changed/added files for this implementation:

- Backend API/configuration: `app/api/projects.py`, `app/api/runtime.py`, `app/models/api.py`,
  `app/core/config.py`, `.env.example`.
- Snapshot/execution services: `app/services/experiment_snapshot.py`, `app/services/code_version.py`,
  `app/services/semantics.py`, `app/services/evaluation.py`, `app/services/ground_truth.py`,
  `app/services/hashing.py`, `app/services/runtime_cache.py`, `app/services/embeddings.py`,
  `app/services/rerankers.py`, `app/adapters/vectorstores/qdrant_store.py`.
- UI: `ui/src/api/client.ts`, `ui/src/components/ExperimentProvenance.tsx`,
  `ui/src/pages/IndexingPage.tsx`, `ui/src/pages/ExperimentResultsPage.tsx`,
  `ui/src/pages/SavedExperimentsPage.tsx`, `ui/src/styles.css`.
- Tests: `tests/test_reproducibility.py`, `tests/test_projects_api.py`,
  `tests/test_ground_truth_slices.py`, `ui/tests/experimentProvenance.test.cjs`.
- Documentation: `AGENTS.md`, `README.md`, `docs/API_CONTRACTS.md`, `docs/ARCHITECTURE.md`,
  `docs/CURRENT_STATE.md`, `docs/DEVELOPMENT_WORKFLOW.md`, `docs/DOMAIN_MODEL.md`,
  `docs/PRODUCT_SPEC.md`, `docs/REPRODUCIBILITY.md`.

Verification on 2026-09-06:

- `.venv/Scripts/python.exe -m pytest tests/test_reproducibility.py -q --tb=short -p no:cacheprovider --basetemp=.pytest_tmp_repro_focused_final`: **51 passed**, 12.44 seconds.
- `.venv/Scripts/python.exe -m pytest -q --tb=short -p no:cacheprovider --basetemp=.pytest_tmp_repro_full_final`: **174 passed**, 17.80 seconds.
- From `ui`, `node tests/experimentProvenance.test.cjs`: **3 passed**;
  `node tests/slicePopulation.test.cjs`: **4 passed**.
- From `ui`, `npm.cmd run build`: **passed** (`tsc -b` and Vite; 48 modules).
- `git diff --check`: **passed**. Git emitted line-ending conversion notices, not whitespace errors.

The backend tests use SQLite and fake Qdrant/model adapters; the concurrent claim test uses separate
connections to a file-backed SQLite database. Live PostgreSQL/Qdrant/provider integration was not run.
Windows sandbox ACLs blocked pytest temporary-directory access on initial attempts; final pytest
commands ran with approved filesystem access. UI rendering tests ran directly in Node because the
sandbox blocked child-process spawning by `node --test`.


### Review fixes verification

The follow-up closes source/prepared input verification, removes the Qwen prompt fallback, and
validates embedding numeric bounds before snapshot creation. Eighteen regression cases cover
missing/mutated required inputs, no ready cache on failure, exact materialization output hashes,
single-buffer text/PDF/Docling processing after file removal, unused sidecars, prompt rejection,
and effective Voyage parameters. Existing synthetic manifest fixtures now include content hashes.

- Focused: `.venv/Scripts/python.exe -m pytest tests/test_reproducibility.py tests/test_parent_units.py -q --tb=short -p no:cacheprovider --basetemp=.pytest_tmp_reviewfix4`: **72 passed**, 14.01 seconds.
- Full: `.venv/Scripts/python.exe -m pytest -q --tb=short -p no:cacheprovider --basetemp=.pytest_tmp_reviewfix_full`: **192 passed**, 18.54 seconds.
- `git diff --check`: **passed**.
- Frontend files were unchanged; UI tests/build were not rerun for this follow-up.
- The initial sandboxed pytest attempt hit Windows temporary-directory ACL errors; final runs used approved access.
- No live Qdrant, Docling or model-provider integration was run. No commit was created.
