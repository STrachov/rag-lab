const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const source = fs.readFileSync(path.join(__dirname, "../src/components/HybridDiagnosticsPanel.tsx"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const components = {};
new Function("require", "exports", compiled)(require, components);
function fixture() {
  return { mode: "hybrid", diagnostics: { fusion: "rrf", rrf_k: 60,
    dense_candidates: [{ chunk_id: "dense-child", page: 2, dense_rank: 1, dense_score: .8 }],
    sparse_candidates: [{ chunk_id: "sparse-child", page: 1, sparse_rank: 1, sparse_score: 9 }],
    fused_candidates: [{ chunk_id: "sparse-child", page: 1, fused_rank: 1, dense_rank: null,
      sparse_rank: 1, dense_contribution: 0, sparse_contribution: 1 / 61, fused_score: 1 / 61 }],
    parent_page_aggregation: { applied: true, strategy: "parent_page_retrieval", parent_score: "max",
      pages: [{ rank: 1, page: 1, page_score: 1 / 61, max_child_chunk_ids: ["sparse-child", "tied-child"],
        child_chunks: [{ chunk_id: "sparse-child", rank: 1, score: 1 / 61 },
                       { chunk_id: "tied-child", rank: 2, score: 1 / 61 }] }] },
  } };
}
const render = retrieval => renderToStaticMarkup(React.createElement(components.HybridDiagnosticsPanel, { retrieval }));

test("hybrid diagnostics are collapsed, read-only and preserve backend scores and max ties", () => {
  const html = render(fixture());
  for (const text of ["Hybrid diagnostics", "Dense top candidates", "Sparse top candidates", "RRF candidates",
    "dense-child", "sparse-child", "dense_rank", "sparse_contribution", "fused_score", "Parent aggregation (max)"])
    assert.ok(html.includes(text), text);
  assert.ok(html.includes(`title="${1 / 61}"`));
  assert.ok(html.includes("<td>—</td>"));
  assert.equal((html.match(/· max/g) || []).length, 2);
  assert.match(html, /<details[^>]*><summary>Hybrid diagnostics/);
  assert.doesNotMatch(html, /<details[^>]*\bopen\b|<input|<select|<button/);
});

test("panel is absent without hybrid response diagnostics", () => {
  assert.equal(render({ mode: "hybrid" }), "");
  assert.equal(render({ mode: "hybrid", diagnostics: null }), "");
  for (const mode of ["dense", "sparse"]) assert.equal(render({ ...fixture(), mode }), "");
});

test("unapplied aggregation and empty candidates are explicit", () => {
  const value = fixture();
  value.diagnostics.dense_candidates = [];
  value.diagnostics.parent_page_aggregation = { applied: false, strategy: "chunk_retrieval", pages: [] };
  const html = render(value);
  assert.ok(html.includes("No candidates."));
  assert.ok(html.includes("Parent-page aggregation was not applied (chunk_retrieval)"));
  assert.ok(!html.includes("Contributing child chunks"));
});

test("display limits do not reorder candidates or compute new results", () => {
  const value = fixture();
  value.diagnostics.dense_candidates = Array.from({ length: 31 }, (_, i) => ({
    chunk_id: `unique-dense-${i}`, page: i, dense_rank: i + 1, dense_score: i }));
  const html = render(value);
  assert.ok(html.includes("unique-dense-29"));
  assert.ok(!html.includes("unique-dense-30"));
  assert.ok(html.indexOf("unique-dense-0") < html.indexOf("unique-dense-29"));
});
