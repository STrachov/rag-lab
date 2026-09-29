const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

const componentSource = fs.readFileSync(
  path.join(__dirname, "../src/components/GroundTruthEvaluationSelector.tsx"),
  "utf8",
);
const compiled = ts.transpileModule(componentSource, {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const components = {};
new Function("require", "exports", compiled)(require, components);

const pageSource = fs.readFileSync(path.join(__dirname, "../src/pages/IndexingPage.tsx"), "utf8");
const assets = [
  { id: "asset-a", name: "Prepared A" },
  { id: "asset-b", name: "Prepared B" },
];
const groundTruthSets = [
  {
    id: "gt-old",
    name: "Old GT",
    data_asset_id: "asset-a",
    metadata_json: { canonical_sha256: "a".repeat(64) },
  },
  {
    id: "gt-new",
    name: "New GT",
    data_asset_id: "asset-a",
    metadata_json: { canonical_sha256: "b".repeat(64) },
  },
  {
    id: "gt-other",
    name: "Other data GT",
    data_asset_id: "asset-b",
    metadata_json: { canonical_sha256: "c".repeat(64) },
  },
  {
    id: "gt-unlinked",
    name: "Unlinked GT",
    data_asset_id: null,
    metadata_json: {},
  },
];

test("multiple GT sets remain explicitly unselected after loading", () => {
  const compatible = components.compatibleGroundTruthSets(groundTruthSets, "asset-a");
  assert.equal(components.reconcileGroundTruthSelection("", compatible), "");
  assert.equal(components.hasValidGroundTruthSelection("", compatible), false);
  assert.doesNotMatch(pageSource, /groundTruthResult\.ground_truth_sets\[0\]/);
});

test("evaluation selector is always rendered in the Ground Truth Evaluation panel", () => {
  assert.match(
    pageSource,
    /<h2>Ground Truth Evaluation<\/h2>[\s\S]*?<GroundTruthEvaluationSelector/,
  );
  const html = renderToStaticMarkup(
    React.createElement(components.GroundTruthEvaluationSelector, {
      dataAssets: assets,
      groundTruthSets: components.compatibleGroundTruthSets(groundTruthSets, "asset-a"),
      onChange: () => {},
      selectedGroundTruthSetId: "",
    }),
  );
  assert.match(html, /Select a Ground Truth Set/);
  assert.match(html, /Old GT · Prepared A · SHA a{12}/);
  assert.match(html, /Unlinked GT · unlinked/);
});

test("GT sets linked to another data asset are not offered for evaluation", () => {
  const compatible = components.compatibleGroundTruthSets(groundTruthSets, "asset-a");
  assert.deepEqual(compatible.map((item) => item.id), ["gt-old", "gt-new", "gt-unlinked"]);
  assert.equal(components.compatibleGroundTruthSets(groundTruthSets, null).length, 0);
});

test("Run evaluation requires a compatible explicit selection", () => {
  const compatible = components.compatibleGroundTruthSets(groundTruthSets, "asset-a");
  assert.equal(components.hasValidGroundTruthSelection("", compatible), false);
  assert.equal(components.hasValidGroundTruthSelection("gt-other", compatible), false);
  assert.equal(components.hasValidGroundTruthSelection("gt-new", compatible), true);
  assert.match(pageSource, /!selectedGroundTruthSet/);
  assert.ok(pageSource.includes("Select a Ground Truth Set before running evaluation."));
});

test("explicitly selected GT is sent when SavedExperiment is created", () => {
  assert.match(pageSource, /ground_truth_set_id: selectedGroundTruthSet\.id/);
});

test("removed GT resets selection and reordered lists never silently switch it", () => {
  const compatible = components.compatibleGroundTruthSets(groundTruthSets, "asset-a");
  assert.equal(components.reconcileGroundTruthSelection("gt-new", compatible), "gt-new");
  assert.equal(
    components.reconcileGroundTruthSelection("gt-new", [...compatible].reverse()),
    "gt-new",
  );
  assert.equal(
    components.reconcileGroundTruthSelection(
      "gt-new",
      compatible.filter((item) => item.id !== "gt-new"),
    ),
    "",
  );
});
