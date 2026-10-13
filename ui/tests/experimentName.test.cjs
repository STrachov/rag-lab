const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/utils/experimentName.ts"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const helpers = {};
new Function("require", "exports", compiled)(require, helpers);

const chunksCache = {
  metadata_json: {
    chunking: {
      strategy: "page_recursive",
      params: { chunk_size: 500, chunk_overlap: 75 },
    },
  },
};
const hybridIndex = {
  metadata_json: {
    embedding: { model: "voyage-4-lite", model_id: "voyage_4_lite" },
    index_mode: "hybrid",
    sparse: { model_id: "bm25_local" },
  },
};
const sparseModels = [{ id: "bm25_local", label: "BM25 local" }];

test("evaluation name describes the selected controlled configuration", () => {
  const name = helpers.defaultEvaluationExperimentName(
    { name: "Wheeler GTv2" },
    chunksCache,
    hybridIndex,
    "dense",
    { label: "Voyage rerank-2.5" },
    sparseModels,
  );

  assert.equal(
    name,
    "Wheeler GTv2 / page-recursive 500/75 / hybrid voyage-4-lite + BM25 local / dense / Voyage rerank-2.5",
  );
});

test("evaluation name reports disabled reranking and omits unused sparse model", () => {
  const denseIndex = {
    metadata_json: {
      embedding: { model: "intfloat/multilingual-e5-small" },
      index_mode: "dense",
      sparse: null,
    },
  };

  assert.equal(
    helpers.defaultEvaluationExperimentName(
      { name: "Baseline" },
      chunksCache,
      denseIndex,
      "dense",
      null,
      sparseModels,
    ),
    "Baseline / page-recursive 500/75 / dense intfloat/multilingual-e5-small / dense / wo reranker",
  );
});
