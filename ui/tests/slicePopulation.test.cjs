const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

// Transpile the actual shared detail/Compare components in memory; no generated files.
const source = fs.readFileSync(path.join(__dirname, "../src/components/SlicePopulation.tsx"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const components = {};
new Function("require", "exports", compiled)(require, components);
const population = (slice) => renderToStaticMarkup(React.createElement(components.SlicePopulation, { slice }));

test("partial slices show completion, errors and an incomplete warning", () => {
  const html = population({ question_count: 3, completed_question_count: 1, error_count: 2 });
  assert.match(html, /1\/3 completed/);
  assert.match(html, /2 errors/);
  assert.match(html, /Incomplete: metrics use completed rows only/);
});

test("fully failed slices cannot appear complete", () => {
  const html = population({ question_count: 3, completed_question_count: 0, error_count: 3 });
  assert.match(html, /0\/3 completed/);
  assert.match(html, /no questions completed successfully/);
});

test("complete slices and legacy slices are distinguished", () => {
  assert.doesNotMatch(population({ question_count: 3, completed_question_count: 3, error_count: 0 }), /Incomplete/);
  assert.match(population({ question_count: 3 }), /completion not recorded/);
  assert.match(population({}), /completion not recorded/);
});

test("metric-specific denominator is visible, without inventing legacy counts", () => {
  const render = (props) => renderToStaticMarkup(React.createElement(components.SliceMetricValue, props));
  assert.match(render({ value: 1, count: 1 }), /1\.000 \(n=1\)/);
  assert.match(render({ value: 0.5, count: 2 }), /0\.500 \(n=2\)/);
  assert.doesNotMatch(render({ value: 1 }), /n=/);
  assert.match(render({}), />-</);
});
