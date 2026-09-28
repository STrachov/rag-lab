const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const clientSource = fs.readFileSync(path.join(__dirname, "../src/api/client.ts"), "utf8");
const pageSource = fs.readFileSync(path.join(__dirname, "../src/pages/GroundTruthPage.tsx"), "utf8");

test("API client deletes the project-scoped ground truth endpoint", () => {
  assert.match(
    clientSource,
    /request\(`\/projects\/\$\{projectId\}\/ground-truth-sets\/\$\{groundTruthSetId\}`,[\s\S]*?method: "DELETE"/,
  );
});

test("successful deletion removes the row without a browser reload", () => {
  assert.match(pageSource, /await deleteGroundTruthSet\(currentProject\.id, groundTruthSet\.id\)/);
  assert.match(
    pageSource,
    /setGroundTruthSets\(\(current\) => current\.filter\(\(item\) => item\.id !== groundTruthSet\.id\)\)/,
  );
  assert.doesNotMatch(pageSource, /window\.location\.reload/);
});

test("deletion confirms ownership cleanup, blocks duplicates and exposes API errors", () => {
  for (const text of [
    "Удалить Ground Truth Set",
    "Будут удалены GT set и принадлежащие ему сохранённые artifacts.",
    "Это действие нельзя отменить.",
  ]) {
    assert.ok(pageSource.includes(text), text);
  }
  assert.match(pageSource, /disabled=\{deletingId !== null\}/);
  assert.match(pageSource, /setError\(err instanceof Error \? err\.message/);
  assert.match(pageSource, /Ground truth unavailable: \{error\}/);
});

test("delete is separated from file downloads inside the actions column", () => {
  assert.match(pageSource, /className="ground-truth-actions"/);
  assert.match(pageSource, /className="ground-truth-downloads"/);
  assert.ok(pageSource.indexOf('className="ground-truth-downloads"') < pageSource.indexOf('className="text-action danger"'));
});
