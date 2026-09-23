const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

const source = fs.readFileSync(path.join(__dirname, "../src/components/ExperimentProvenance.tsx"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const components = {};
new Function("require", "exports", compiled)(require, components);
const experiment = () => ({
  id: "one", code_commit: "a".repeat(40),
  metrics_summary_json: { evaluation: { code: { dirty: true } } },
  params_snapshot_json: {
    data: { source: { manifest_hash: "source-hash", files: [{ original_name: "synthetic.pdf" }] },
      prepared: { manifest_hash: "prepared-hash" }, preparation: { method_id: "docling", params: { do_ocr: false } } },
    chunking: { strategy: "recursive", params: { chunk_size: 300, chunk_overlap: 50 },
      size_unit: "approx_whitespace_tokens", chunks_file_sha256: "c".repeat(64) },
    embedding: { model: "synthetic-model", params: { normalize: true } }, sparse: null,
    index: { cache_id: "index-1", collection_name: "physical-1", mode: "dense", distance: "Cosine" },
    retrieval: { top_k: 5 }, reranking: null, ground_truth: { canonical_sha256: "d".repeat(64) },
    semantics: { retrieval_version: "raglab.retrieval.v1", evaluation_version: "raglab.gt_eval.v1" },
  },
});

test("detail displays historical provenance, units, hashes, semantics and dirty code", () => {
  const html = renderToStaticMarkup(React.createElement(components.ExperimentProvenance, { experiment: experiment() }));
  for (const expected of ["synthetic.pdf", "source-hash", "prepared-hash", "docling", "300 / 50",
    "approx_whitespace_tokens", "synthetic-model", "physical-1", "raglab.gt_eval.v1", "dirty"])
    assert.ok(html.includes(expected), expected);
  assert.ok(html.includes('title="' + "c".repeat(64) + '"'));
});

test("Compare flags each differing controlled variable", () => {
  const first = experiment();
  const second = experiment();
  second.id = "two";
  second.code_commit = "b".repeat(40);
  const s = second.params_snapshot_json;
  s.data.source.manifest_hash = "different-source";
  s.data.prepared.manifest_hash = "different-prepared";
  s.embedding.model = "other-model";
  s.retrieval.top_k = 10;
  s.reranking = { model: "reranker" };
  s.ground_truth.canonical_sha256 = "other-gt";
  s.semantics.evaluation_version = "raglab.gt_eval.v2";
  const html = renderToStaticMarkup(React.createElement(components.ProvenanceComparison, { experiments: [first, second] }));
  for (const label of ["Source manifest", "Prepared manifest", "Embedding", "Retrieval", "Reranker",
    "GT canonical SHA-256", "Semantics", "Code commit"])
    assert.ok(html.includes(label + " — differs"), label);
});

test("equal configuration does not get a difference warning from JSON key order", () => {
  const first = experiment();
  const second = experiment();
  second.id = "two";
  second.params_snapshot_json.embedding = { params: { normalize: true }, model: "synthetic-model" };
  const html = renderToStaticMarkup(React.createElement(components.ProvenanceComparison, { experiments: [first, second] }));
  assert.ok(!html.includes(" — differs"));
});
