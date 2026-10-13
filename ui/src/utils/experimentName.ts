import type { DerivedCache, GroundTruthSet, RerankerModel, SparseModel } from "../api/client";

export function defaultEvaluationExperimentName(
  groundTruthSet: GroundTruthSet | null,
  chunksCache: DerivedCache | null,
  indexCache: DerivedCache,
  retrievalMode: "dense" | "sparse" | "hybrid",
  rerankerModel: RerankerModel | null,
  sparseModels: SparseModel[],
): string {
  const groundTruthName = groundTruthSet?.name?.trim() || "GT";
  const chunkingName = chunkingExperimentName(chunksCache);
  const indexName = indexExperimentName(indexCache, sparseModels);
  const rerankerName = rerankerModel?.label.trim() || "wo reranker";
  return `${groundTruthName} / ${chunkingName} / ${indexName} / ${retrievalMode} / ${rerankerName}`;
}

function chunkingExperimentName(cache: DerivedCache | null): string {
  const chunking = objectValue(cache?.metadata_json.chunking);
  const params = objectValue(chunking?.params);
  const strategy = stringValue(chunking?.strategy).replace(/_/g, "-") || "chunking";
  const chunkSize = numberValue(params?.chunk_size);
  const chunkOverlap = numberValue(params?.chunk_overlap);
  return chunkSize !== null && chunkOverlap !== null
    ? `${strategy} ${chunkSize}/${chunkOverlap}`
    : strategy;
}

function indexExperimentName(indexCache: DerivedCache, sparseModels: SparseModel[]): string {
  const indexMode = stringValue(indexCache.metadata_json.index_mode) || "dense";
  const denseModel = embeddingModelName(indexCache) || "dense model";
  const sparse = objectValue(indexCache.metadata_json.sparse);
  const sparseModelId = stringValue(sparse?.model_id);
  const sparseModel = sparseModels.find((model) => model.id === sparseModelId);
  const sparseName = sparseModel?.label.trim() || sparseModelId || "sparse model";

  if (indexMode === "dense") {
    return `${indexMode} ${denseModel}`;
  }
  if (indexMode === "sparse") {
    return `${indexMode} ${sparseName}`;
  }
  return `${indexMode} ${denseModel} + ${sparseName}`;
}

function embeddingModelName(cache: DerivedCache): string {
  const embedding = objectValue(cache.metadata_json.embedding);
  return stringValue(embedding?.model) || stringValue(embedding?.model_id);
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
