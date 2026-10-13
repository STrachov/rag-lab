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

test("JSON export preserves the full saved record, precision, failures and all questions", () => {
  const original = JSON.stringify(experiment);
  const result = JSON.parse(JSON.stringify(helpers.buildExperimentExport(project, experiment, "2026-10-13T12:00:00Z")));
  assert.equal(result.schema_version, "raglab.experiment_export.v1");
  assert.equal(result.exported_at, "2026-10-13T12:00:00Z");
  assert.deepEqual(result.project, { id: project.id, name: project.name });
  assert.deepEqual(result.saved_experiment, experiment);
  assert.equal(JSON.stringify(experiment), original);
  assert.equal(result.analysis_context.failed_questions_are_zero_scores, false);
  assert.equal(result.analysis_context.retrieved_text_included, false);
});

test("unevaluated experiments export their actual empty results without invented metrics", () => {
  const pending = { ...experiment, status: "created", metrics_summary_json: {} };
  const result = helpers.buildExperimentExport(project, pending);
  assert.deepEqual(result.saved_experiment.metrics_summary_json, {});
  assert.equal(result.saved_experiment.status, "created");
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
  assert.deepEqual(JSON.parse(await blob.text()).saved_experiment, experiment);
  assert.ok(clicked && removed);
  cleanup();
  assert.ok(revoked);
});
