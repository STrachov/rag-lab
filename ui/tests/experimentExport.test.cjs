const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/utils/experimentExport.ts"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const helpers = {};
new Function("require", "exports", compiled)(require, helpers);

const project = { id: "project-1", name: "Synthetic project", metadata_json: { unrelated: true } };
const experiment = {
  id: "123456789012abcdef", project_id: project.id, name: "Synthetic experiment",
  status: "completed_with_errors", notes: "Analysis notes",
  params_snapshot_json: {
    ground_truth: { canonical_sha256: "a".repeat(64), annotation_version: "v2" },
    retrieval: { top_k: 5 },
    chunking: { strategy: "page_recursive", chunks_file_sha256: "chunks-hash", cache_key: "internal" },
    index: { mode: "hybrid", collection_name: "internal-collection" },
  },
  metrics_summary_json: {
    metric_averages: { page_recall_at_k: 1 / 3 },
    metric_question_counts: { page_recall_at_k: 1 },
    slice_metrics: { hard: { completed_question_count: 1, error_count: 1 } },
    questions: [
      { question_id: "q1", question: "Пример?", status: "completed", metrics: { page_recall_at_k: 1 / 3 } },
      { question_id: "q2", status: "failed", metrics: {}, error_json: { message: "Failure" } },
    ],
  },
  error_json: null, code_commit: "revision", params_hash: "hash", future_field: { preserved: true },
};

test("compact export preserves analytical results, provenance and precision without mutating the record", () => {
  const original = JSON.stringify(experiment);
  const result = JSON.parse(JSON.stringify(helpers.buildExperimentExport(project, experiment, "2026-10-13T12:00:00Z")));
  assert.equal(result.schema_version, "raglab.experiment_export.v2");
  assert.equal(result.exported_at, "2026-10-13T12:00:00Z");
  assert.deepEqual(result.project, { name: project.name });
  assert.equal(result.experiment.status, experiment.status);
  assert.deepEqual(result.configuration.retrieval, { top_k: 5 });
  assert.deepEqual(result.configuration.index, { mode: "hybrid" });
  assert.deepEqual(result.configuration.chunking, { strategy: "page_recursive" });
  assert.equal(result.provenance.chunks_sha256, "chunks-hash");
  assert.equal(result.provenance.ground_truth.canonical_sha256, "a".repeat(64));
  assert.deepEqual(result.summary.metric_averages, experiment.metrics_summary_json.metric_averages);
  assert.deepEqual(result.summary.metric_question_counts, experiment.metrics_summary_json.metric_question_counts);
  assert.deepEqual(result.summary.slice_metrics, experiment.metrics_summary_json.slice_metrics);
  assert.equal(result.questions.length, 2);
  assert.equal(result.questions[1].error_json.message, "Failure");
  assert.equal(JSON.stringify(experiment), original);
  assert.equal(result.analysis_context.failed_questions_are_zero_scores, false);
  assert.equal(result.analysis_context.retrieved_text_included, false);
});

test("unevaluated experiments export their actual empty results without invented metrics", () => {
  const pending = { ...experiment, status: "created", metrics_summary_json: {} };
  const result = helpers.buildExperimentExport(project, pending);
  assert.equal(result.summary, undefined);
  assert.equal(result.questions, undefined);
  assert.equal(result.experiment.status, "created");
  assert.ok(Number.isFinite(Date.parse(result.exported_at)));
});

test("download produces a UTF-8 JSON file and cleans up its temporary resources", async () => {
  let blob;
  let clicked = false;
  let removed = false;
  let revoked = false;
  let cleanup;
  const anchor = { click() { clicked = true; }, remove() { removed = true; } };
  const browserHelpers = {};
  new Function("require", "exports", "document", "window", "URL", compiled)(
    require, browserHelpers,
    { createElement: () => anchor, body: { appendChild: (value) => assert.equal(value, anchor) } },
    { setTimeout: (callback) => { cleanup = callback; } },
    { createObjectURL: (value) => { blob = value; return "blob:test"; }, revokeObjectURL: (url) => { assert.equal(url, "blob:test"); revoked = true; } },
  );
  browserHelpers.downloadExperimentExport(project, experiment);
  assert.equal(anchor.download, "raglab-experiment-123456789012.json");
  assert.equal(anchor.href, "blob:test");
  assert.equal(blob.type, "application/json;charset=utf-8");
  assert.equal(JSON.parse(await blob.text()).experiment.id, experiment.id);
  assert.ok(clicked && removed);
  cleanup();
  assert.ok(revoked);
});

test("sources, page numbering, configuration and top results are deduplicated without losing ranks or usage", () => {
  const retrieved = { source_name: "abc.pdf", page: 7, rank: 1, original_rank: 4, dense_score: 0.4, rerank_score: 0.8 };
  const item = {
    ...experiment,
    metrics_summary_json: {
      ...experiment.metrics_summary_json,
      evaluation: { retrieval: { top_k: 5 }, code: { commit: "revision", dirty: true }, usage: { reranking: { total_tokens: 100 } } },
      questions: [{
        question_id: "q1", expected_answer_type: "found", top_result: retrieved,
        ground_truth: { expected_answer_type: "found", relevant_pages: [{ pdf_sha1: "abc", page_index: 6, page_number: 7 }] },
        retrieved: [retrieved], question_metadata: { page_level_limitation: false, tags: ["hard"] },
        metrics: { page_hit_at_k: 0 }, usage: { reranking: { provider: "voyage", model: "rerank", total_tokens: 100, retry_count: 0 } },
      }],
    },
  };
  const result = helpers.buildExperimentExport(project, item);
  assert.deepEqual(result.sources, [{ id: "s1", identity: "abc", name: "abc.pdf" }]);
  assert.deepEqual(result.questions[0].ground_truth.relevant_pages, [{ source_id: "s1", page_number: 7 }]);
  assert.equal(result.questions[0].retrieved[0].source_id, "s1");
  assert.equal(result.questions[0].retrieved[0].original_rank, 4);
  assert.equal(result.questions[0].retrieved[0].rerank_score, 0.8);
  assert.equal(result.questions[0].question_metadata.page_level_limitation, false);
  assert.equal(result.questions[0].metrics.page_hit_at_k, 0);
  assert.deepEqual(result.questions[0].usage.reranking, { total_tokens: 100, retry_count: 0 });
  assert.equal(result.questions[0].top_result, undefined);
  assert.equal(result.questions[0].expected_answer_type, undefined);
  assert.equal(result.summary.retrieval, undefined);
  assert.deepEqual(result.provenance.code, { commit: "revision", dirty: true });
});
