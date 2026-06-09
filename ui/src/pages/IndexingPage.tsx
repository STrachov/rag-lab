import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  createParameterSet,
  createQdrantIndex,
  createSavedExperiment,
  DataAsset,
  deleteDerivedCache,
  deleteParameterSet,
  DerivedCache,
  EmbeddingModel,
  EmbeddingParamValue,
  evaluateSavedExperiment,
  GroundTruthQuestion,
  GroundTruthRankingScore,
  GroundTruthSet,
  listDataAssets,
  listDerivedCaches,
  listEmbeddingModels,
  listGroundTruthQuestions,
  listGroundTruthSets,
  listParameterSets,
  listRerankerModels,
  listSparseModels,
  ParameterSet,
  previewRerank,
  previewRetrieval,
  Project,
  RerankerModel,
  RetrievalPreviewResponse,
  SavedExperiment,
  scoreGroundTruthRanking,
  SparseModel,
} from "../api/client";

type IndexingPageProps = {
  currentProject: Project | null;
};

export function IndexingPage({ currentProject }: IndexingPageProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [dataAssets, setDataAssets] = useState<DataAsset[]>([]);
  const [parameterSets, setParameterSets] = useState<ParameterSet[]>([]);
  const [embeddingModels, setEmbeddingModels] = useState<EmbeddingModel[]>([]);
  const [sparseModels, setSparseModels] = useState<SparseModel[]>([]);
  const [rerankerModels, setRerankerModels] = useState<RerankerModel[]>([]);
  const [groundTruthSets, setGroundTruthSets] = useState<GroundTruthSet[]>([]);
  const [groundTruthQuestions, setGroundTruthQuestions] = useState<GroundTruthQuestion[]>([]);
  const [chunksCacheId, setChunksCacheId] = useState(searchParams.get("chunks_cache_id") ?? "");
  const [chunkCaches, setChunkCaches] = useState<DerivedCache[]>([]);
  const [indexCaches, setIndexCaches] = useState<DerivedCache[]>([]);
  const [selectedIndexCacheId, setSelectedIndexCacheId] = useState("");
  const [selectedRetrievalParameterSetId, setSelectedRetrievalParameterSetId] = useState("");
  const [retrievalPresetName, setRetrievalPresetName] = useState("Retrieval baseline");
  const [retrievalPresetDescription, setRetrievalPresetDescription] = useState("");
  const [embeddingModelId, setEmbeddingModelId] = useState("intfloat_multilingual_e5_small");
  const [embeddingParams, setEmbeddingParams] = useState<Record<string, EmbeddingParamValue>>({});
  const [sparseModelId, setSparseModelId] = useState("bm25_local");
  const [sparseParams, setSparseParams] = useState<Record<string, EmbeddingParamValue>>({});
  const [indexMode, setIndexMode] = useState<"dense" | "sparse" | "hybrid">("hybrid");
  const [retrievalMode, setRetrievalMode] = useState<"dense" | "sparse" | "hybrid">("hybrid");
  const [retrievalStrategy, setRetrievalStrategy] = useState<"chunk_retrieval" | "parent_page_retrieval" | "parent_chapter_retrieval">("chunk_retrieval");
  const [parentScore, setParentScore] = useState<"max" | "mean" | "sum">("max");
  const [questionSource, setQuestionSource] = useState<"manual" | "ground_truth">("manual");
  const [selectedGroundTruthSetId, setSelectedGroundTruthSetId] = useState("");
  const [selectedGroundTruthQuestionId, setSelectedGroundTruthQuestionId] = useState("");
  const [query, setQuery] = useState("Where from is Wayne Xin Zhao?");
  const [topK, setTopK] = useState(5);
  const [candidateK, setCandidateK] = useState(30);
  const [retrievalCacheId, setRetrievalCacheId] = useState("");
  const [rerankerModelId, setRerankerModelId] = useState("baai_bge_reranker_v2_m3");
  const [rerankerParams, setRerankerParams] = useState<Record<string, EmbeddingParamValue>>({});
  const [retrievalResult, setRetrievalResult] = useState<RetrievalPreviewResponse | null>(null);
  const [rerankResult, setRerankResult] = useState<RetrievalPreviewResponse | null>(null);
  const [retrievalMetrics, setRetrievalMetrics] = useState<GroundTruthRankingScore | null>(null);
  const [rerankMetrics, setRerankMetrics] = useState<GroundTruthRankingScore | null>(null);
  const [evaluationExperiment, setEvaluationExperiment] = useState<SavedExperiment | null>(null);
  const [isSavingRetrievalPreset, setIsSavingRetrievalPreset] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [isRetrieving, setIsRetrieving] = useState(false);
  const [isReranking, setIsReranking] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluateWithReranking, setEvaluateWithReranking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const preparedAssets = useMemo(
    () => dataAssets.filter((asset) => asset.asset_type === "prepared"),
    [dataAssets],
  );
  const retrievalParameterSets = useMemo(
    () => parameterSets.filter((set) => set.category === "retrieval"),
    [parameterSets],
  );
  const selectedModel = embeddingModels.find((model) => model.id === embeddingModelId);
  const selectedSparseModel = sparseModels.find((model) => model.id === sparseModelId);
  const selectedRerankerModel = rerankerModels.find((model) => model.id === rerankerModelId);
  const selectedChunksCache = chunkCaches.find((cache) => cache.id === chunksCacheId) ?? null;
  const linkedIndexCaches = selectedChunksCache
    ? indexCaches.filter((cache) => cacheBelongsToChunks(cache, selectedChunksCache))
    : indexCaches;
  const selectedIndexCache = linkedIndexCaches.find((cache) => cache.id === selectedIndexCacheId) ?? linkedIndexCaches[0] ?? null;
  const selectedGroundTruthQuestion =
    groundTruthQuestions.find((question) => question.question_id === selectedGroundTruthQuestionId) ?? null;
  const indexingEstimate = selectedChunksCache ? cacheIndexingEstimate(selectedChunksCache) : null;
  const rerankCandidateCount = retrievalCacheId
    ? (rerankResult?.candidate_k ?? retrievalResult?.candidate_k ?? candidateK)
    : 0;
  const retrievalSnapshot = {
    retrieval: {
      candidate_k: candidateK,
      mode: retrievalMode,
      parent_score: parentScore,
      strategy: retrievalStrategy,
      top_k: topK,
    },
    reranking: selectedRerankerModel
      ? {
          model_id: rerankerModelId,
          params: rerankerParams,
        }
      : null,
  };

  useEffect(() => {
    if (!currentProject) {
      setDataAssets([]);
      setParameterSets([]);
      setEmbeddingModels([]);
      setSparseModels([]);
      setRerankerModels([]);
      setGroundTruthSets([]);
      setGroundTruthQuestions([]);
      setChunkCaches([]);
      setIndexCaches([]);
      return;
    }

    Promise.all([
      listDataAssets(currentProject.id),
      listDerivedCaches(currentProject.id, "chunks"),
      listDerivedCaches(currentProject.id, "qdrant_index"),
      listParameterSets(currentProject.id),
      listEmbeddingModels(currentProject.id),
      listSparseModels(currentProject.id),
      listRerankerModels(currentProject.id),
      listGroundTruthSets(currentProject.id),
    ])
      .then(([assetResult, chunksResult, indexResult, parameterResult, modelResult, sparseResult, rerankerResult, groundTruthResult]) => {
        setDataAssets(assetResult.data_assets);
        setChunkCaches(chunksResult.derived_caches);
        setIndexCaches(indexResult.derived_caches);
        setParameterSets(parameterResult.parameter_sets);
        setEmbeddingModels(modelResult.models);
        setSparseModels(sparseResult.models);
        setRerankerModels(rerankerResult.models);
        setGroundTruthSets(groundTruthResult.ground_truth_sets);
        setSelectedGroundTruthSetId((current) => current || groundTruthResult.ground_truth_sets[0]?.id || "");
        const urlChunksCacheId = searchParams.get("chunks_cache_id") ?? "";
        const firstChunksCache = chunksResult.derived_caches[0]?.id ?? "";
        setChunksCacheId((current) => current || urlChunksCacheId || firstChunksCache);
        const firstRetrievalSet = parameterResult.parameter_sets.find((set) => set.category === "retrieval");
        setSelectedRetrievalParameterSetId((current) => current || firstRetrievalSet?.id || "");
        const firstModel = modelResult.models[0];
        if (firstModel) {
          setEmbeddingModelId((current) => current || firstModel.id);
          setEmbeddingParams((current) =>
            Object.keys(current).length > 0 ? current : firstModel.default_params,
          );
        }
        const firstSparseModel = sparseResult.models[0];
        if (firstSparseModel) {
          setSparseModelId((current) => current || firstSparseModel.id);
          setSparseParams((current) =>
            Object.keys(current).length > 0 ? current : firstSparseModel.default_params,
          );
        }
        const firstRerankerModel = rerankerResult.models[0];
        if (firstRerankerModel) {
          setRerankerModelId((current) => current || firstRerankerModel.id);
          setRerankerParams((current) =>
            Object.keys(current).length > 0 ? current : firstRerankerModel.default_params,
          );
        }
        const firstReadyIndex = indexResult.derived_caches.find((cache) => cache.status === "ready");
        setSelectedIndexCacheId((current) => current || firstReadyIndex?.id || indexResult.derived_caches[0]?.id || "");
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [currentProject, searchParams]);

  useEffect(() => {
    if (!currentProject || !selectedGroundTruthSetId) {
      setGroundTruthQuestions([]);
      setSelectedGroundTruthQuestionId("");
      return;
    }
    listGroundTruthQuestions(currentProject.id, selectedGroundTruthSetId)
      .then((result) => {
        setGroundTruthQuestions(result.questions);
        setSelectedGroundTruthQuestionId((current) => current || result.questions[0]?.question_id || "");
      })
      .catch((err: Error) => setError(err.message));
  }, [currentProject, selectedGroundTruthSetId]);

  useEffect(() => {
    if (!linkedIndexCaches.some((cache) => cache.id === selectedIndexCacheId)) {
      setSelectedIndexCacheId(linkedIndexCaches[0]?.id ?? "");
    }
  }, [linkedIndexCaches, selectedIndexCacheId]);

  useEffect(() => {
    if (questionSource !== "ground_truth") {
      return;
    }
    const selectedQuestion = groundTruthQuestions.find(
      (question) => question.question_id === selectedGroundTruthQuestionId,
    );
    if (selectedQuestion) {
      setQuery(selectedQuestion.question);
      setRetrievalMetrics(null);
      setRerankMetrics(null);
    }
  }, [groundTruthQuestions, questionSource, selectedGroundTruthQuestionId]);

  useEffect(() => {
    const model = embeddingModels.find((item) => item.id === embeddingModelId);
    if (model) {
      setEmbeddingParams(model.default_params);
    }
  }, [embeddingModelId, embeddingModels]);

  useEffect(() => {
    const model = sparseModels.find((item) => item.id === sparseModelId);
    if (model) {
      setSparseParams(model.default_params);
    }
  }, [sparseModelId, sparseModels]);

  useEffect(() => {
    const model = rerankerModels.find((item) => item.id === rerankerModelId);
    if (model) {
      setRerankerParams(model.default_params);
    }
  }, [rerankerModelId, rerankerModels]);

  function handleChunksCacheChange(cacheId: string) {
    setChunksCacheId(cacheId);
    setSearchParams(cacheId ? { chunks_cache_id: cacheId } : {});
    setSelectedIndexCacheId("");
    setRetrievalResult(null);
    setRerankResult(null);
    setRetrievalMetrics(null);
    setRerankMetrics(null);
    setRetrievalCacheId("");
  }

  async function handleIndex(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentProject || !chunksCacheId || !selectedModel) {
      return;
    }
    setIsIndexing(true);
    try {
      const cache = await createQdrantIndex(currentProject.id, {
        chunks_cache_id: chunksCacheId,
        distance: "Cosine",
        embedding: {
          model_id: selectedModel.id,
          params: embeddingParams,
        },
        index_mode: indexMode,
        sparse:
          indexMode === "dense" || !selectedSparseModel
            ? null
            : {
                model_id: selectedSparseModel.id,
                params: sparseParams,
              },
      });
      setIndexCaches((current) => upsertCache(current, cache));
      setSelectedIndexCacheId(cache.id);
      setRetrievalResult(null);
      setRerankResult(null);
      setRetrievalMetrics(null);
      setRerankMetrics(null);
      setRetrievalCacheId("");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create Qdrant index");
      refreshIndexCaches(currentProject.id);
    } finally {
      setIsIndexing(false);
    }
  }

  async function handleSaveRetrievalPreset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentProject || !retrievalPresetName.trim()) {
      return;
    }
    setIsSavingRetrievalPreset(true);
    try {
      const paramsHash = `sha256:${await sha256Hex(stableStringify(retrievalSnapshot))}`;
      const parameterSet = await createParameterSet(currentProject.id, {
        category: "retrieval",
        description: retrievalPresetDescription.trim() || undefined,
        name: retrievalPresetName.trim(),
        params_hash: paramsHash,
        params_json: retrievalSnapshot,
      });
      setParameterSets((current) => [...current, parameterSet]);
      setSelectedRetrievalParameterSetId(parameterSet.id);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save retrieval ParameterSet");
    } finally {
      setIsSavingRetrievalPreset(false);
    }
  }

  function handleApplyRetrievalPreset(parameterSet: ParameterSet) {
    const retrieval = parameterSet.params_json.retrieval;
    if (!isRetrievalParams(retrieval)) {
      setError("Selected ParameterSet does not contain a valid retrieval snapshot");
      return;
    }
    setRetrievalMode(retrieval.mode);
    setRetrievalStrategy(retrieval.strategy);
    setParentScore(retrieval.parent_score);
    setTopK(retrieval.top_k);
    setCandidateK(retrieval.candidate_k);
    const reranking = parameterSet.params_json.reranking;
    if (isRerankingParams(reranking)) {
      setRerankerModelId(reranking.model_id);
      setRerankerParams(reranking.params);
    }
    setRetrievalPresetName(parameterSet.name);
    setRetrievalPresetDescription(parameterSet.description ?? "");
    setSelectedRetrievalParameterSetId(parameterSet.id);
    setRetrievalResult(null);
    setRerankResult(null);
    setRetrievalMetrics(null);
    setRerankMetrics(null);
    setError(null);
  }

  async function handleDeleteSelectedRetrievalPreset() {
    const selected = retrievalParameterSets.find((item) => item.id === selectedRetrievalParameterSetId);
    if (!currentProject || !selected) {
      return;
    }
    if (!window.confirm(`Delete retrieval ParameterSet "${selected.name}"?`)) {
      return;
    }
    try {
      await deleteParameterSet(currentProject.id, selected.id);
      setParameterSets((current) => current.filter((item) => item.id !== selected.id));
      setSelectedRetrievalParameterSetId("");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete retrieval ParameterSet");
    }
  }

  async function handleDeleteSelectedIndexCache() {
    if (!currentProject || !selectedIndexCache) {
      return;
    }
    const label = String(selectedIndexCache.metadata_json.collection_name ?? selectedIndexCache.cache_key);
    const message = [
      `Delete selected index "${label}"?`,
      "This will also remove dependent retrieval preview caches created from this index.",
      "Chunks and prepared data will stay unchanged.",
    ].join("\n\n");
    if (!window.confirm(message)) {
      return;
    }
    try {
      const result = await deleteDerivedCache(currentProject.id, selectedIndexCache.id, {
        cascadeDependents: true,
      });
      setIndexCaches((current) =>
        current.filter((item) => !result.deleted_derived_cache_ids.includes(item.id)),
      );
      setSelectedIndexCacheId("");
      setRetrievalResult(null);
      setRerankResult(null);
      setRetrievalMetrics(null);
      setRerankMetrics(null);
      setRetrievalCacheId("");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete selected index");
    }
  }

  async function handleRetrieve() {
    if (!currentProject || !selectedIndexCache || !query.trim() || selectedIndexCache.status !== "ready") {
      return;
    }
    setIsRetrieving(true);
    try {
      const result = await previewRetrieval(currentProject.id, {
        candidate_k: candidateK,
        index_cache_id: selectedIndexCache.id,
        mode: retrievalMode,
        parent_score: parentScore,
        query: query.trim(),
        strategy: retrievalStrategy,
        top_k: topK,
      });
      setRetrievalResult(result);
      setRerankResult(null);
      setRerankMetrics(null);
      setRetrievalCacheId(result.retrieval_cache_id ?? "");
      const metrics = await scoreSelectedGroundTruth(result);
      setRetrievalMetrics(metrics);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to retrieve chunks");
    } finally {
      setIsRetrieving(false);
    }
  }

  async function handleRerank() {
    if (!currentProject || !retrievalCacheId) {
      return;
    }
    setIsReranking(true);
    try {
      const result = await previewRerank(currentProject.id, {
        retrieval_cache_id: retrievalCacheId,
        reranking: {
          enabled: true,
          model_id: rerankerModelId,
          params: rerankerParams,
        },
        top_k: topK,
      });
      setRerankResult(result);
      const metrics = await scoreSelectedGroundTruth(result);
      setRerankMetrics(metrics);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rerank chunks");
    } finally {
      setIsReranking(false);
    }
  }

  async function handleEvaluateGroundTruth() {
    const dataAssetId = String(selectedIndexCache?.data_asset_id ?? selectedChunksCache?.data_asset_id ?? "");
    if (!currentProject || !selectedIndexCache || !selectedGroundTruthSetId || !dataAssetId) {
      return;
    }
    const snapshot = {
      ground_truth: {
        ground_truth_set_id: selectedGroundTruthSetId,
        question_count: groundTruthQuestions.length,
      },
      index_cache_id: selectedIndexCache.id,
      index_cache_key: selectedIndexCache.cache_key,
      retrieval: {
        candidate_k: candidateK,
        mode: retrievalMode,
        parent_score: parentScore,
        strategy: retrievalStrategy,
        top_k: topK,
      },
      reranking:
        evaluateWithReranking && selectedRerankerModel
          ? {
              enabled: true,
              model_id: selectedRerankerModel.id,
              params: rerankerParams,
            }
          : null,
    };
    setIsEvaluating(true);
    try {
      const paramsHash = `sha256:${await sha256Hex(stableStringify(snapshot))}`;
      const experiment = await createSavedExperiment(currentProject.id, {
        data_asset_id: dataAssetId,
        debug_level: "summary",
        ground_truth_set_id: selectedGroundTruthSetId,
        name: `GT evaluation ${new Date().toISOString().slice(0, 16).replace("T", " ")}`,
        params_hash: paramsHash,
        params_snapshot_json: snapshot,
        pipeline_version: "runtime-v1",
      });
      const evaluated = await evaluateSavedExperiment(currentProject.id, experiment.id, {
        index_cache_id: selectedIndexCache.id,
      });
      setEvaluationExperiment(evaluated);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to evaluate ground truth questions");
    } finally {
      setIsEvaluating(false);
    }
  }

  async function scoreSelectedGroundTruth(
    result: RetrievalPreviewResponse,
  ): Promise<GroundTruthRankingScore | null> {
    if (
      !currentProject ||
      questionSource !== "ground_truth" ||
      !selectedGroundTruthSetId ||
      !selectedGroundTruthQuestionId ||
      !selectedIndexCache
    ) {
      return null;
    }
    return scoreGroundTruthRanking(currentProject.id, selectedGroundTruthSetId, {
      index_cache_id: selectedIndexCache.id,
      k: result.top_k,
      question_id: selectedGroundTruthQuestionId,
      retrieved_chunks: result.retrieved_chunks,
    });
  }

  function refreshIndexCaches(projectId: string) {
    listDerivedCaches(projectId, "qdrant_index")
      .then((result) => {
        setIndexCaches(result.derived_caches);
        setSelectedIndexCacheId((current) => current || result.derived_caches[0]?.id || "");
      })
      .catch((err: Error) => setError(err.message));
  }

  if (!currentProject) {
    return (
      <section className="page">
        <header className="page-header">
          <p className="eyebrow">Retrieval</p>
          <h1>Retrieval</h1>
          <p>Select or create a project first. Index caches are scoped to the current project.</p>
        </header>
        <div className="empty-state">No project selected.</div>
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Retrieval</p>
        <h1>Retrieval & Reranking</h1>
        <p>Materialize normalized chunks, embed them with a registered model, and create a Qdrant index cache.</p>
      </header>

      {error ? <div className="notice">Retrieval unavailable: {error}</div> : null}

      <div className="stage-workbench">
        <div className="stage-left">
          <div className="parameter-section">
            <h2>Chunks Source</h2>
            {chunkCaches.length === 0 ? (
              <div className="nested-empty">Materialize chunks on the Chunking page first.</div>
            ) : (
              <label>
                Materialized chunks
                <select value={chunksCacheId} onChange={(event) => handleChunksCacheChange(event.target.value)}>
                  {chunkCaches.map((cache) => (
                    <option key={cache.id} value={cache.id}>
                      {cacheLabel(cache, preparedAssets)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {selectedChunksCache ? <ChunksCacheSummary cache={selectedChunksCache} assets={preparedAssets} /> : null}
          </div>

          <form className="parameter-section" onSubmit={handleIndex}>
            <h2>Embedding & Sparse</h2>
            <label>
              Index mode
              <select value={indexMode} onChange={(event) => setIndexMode(event.target.value as typeof indexMode)}>
                <option value="hybrid">hybrid</option>
                <option value="dense">dense</option>
                <option value="sparse">sparse</option>
              </select>
            </label>
            <label>
              Dense model
              <select value={embeddingModelId} onChange={(event) => setEmbeddingModelId(event.target.value)}>
                {embeddingModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.label}
                  </option>
                ))}
              </select>
            </label>
            {selectedModel ? (
              <>
                <div className="asset-mini-summary">
                  <span>{selectedModel.provider}</span>
                  <span>{selectedModel.model_name}</span>
                  <span>{effectiveEmbeddingDims(selectedModel, embeddingParams)} dims</span>
                </div>
                <div className="parameter-grid">
                  {selectedModel.fields.map((field) => (
                    <EmbeddingFieldControl
                      field={field}
                      key={field.name}
                      value={embeddingParams[field.name] ?? field.default}
                      onChange={(value) =>
                        setEmbeddingParams((current) => ({ ...current, [field.name]: value }))
                      }
                    />
                  ))}
                </div>
                <p className="form-note">{selectedModel.description}</p>
              </>
            ) : null}
            {indexMode !== "dense" && selectedSparseModel ? (
              <>
                <label>
                  Sparse model
                  <select value={sparseModelId} onChange={(event) => setSparseModelId(event.target.value)}>
                    {sparseModels.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="parameter-grid">
                  {selectedSparseModel.fields.map((field) => (
                    <EmbeddingFieldControl
                      field={field}
                      key={field.name}
                      value={sparseParams[field.name] ?? field.default}
                      onChange={(value) =>
                        setSparseParams((current) => ({ ...current, [field.name]: value }))
                      }
                    />
                  ))}
                </div>
                <p className="form-note">{selectedSparseModel.description}</p>
              </>
            ) : null}
            {indexingEstimate ? (
              <div className="asset-mini-summary">
                <span>{formatInteger(indexingEstimate.chunkCount)} chunks</span>
                <span>{formatEstimatedTokens(indexingEstimate.estimatedTokens)}</span>
              </div>
            ) : null}
            <button className="primary-action" disabled={isIndexing || !chunksCacheId} type="submit">
              {isIndexing ? "Indexing..." : "Create Qdrant index"}
            </button>
          </form>

          <div className="parameter-section">
            <h2>Existing Indexes</h2>
            {linkedIndexCaches.length === 0 ? (
              <div className="nested-empty">No Qdrant index caches for the selected chunks yet.</div>
            ) : (
              <div className="index-cache-list">
                {linkedIndexCaches.map((cache) => (
                  <button
                    className={cache.id === selectedIndexCacheId ? "cache-item selected" : "cache-item"}
                    key={cache.id}
                    onClick={() => {
                      setSelectedIndexCacheId(cache.id);
                      setRetrievalResult(null);
                      setRerankResult(null);
                      setRetrievalMetrics(null);
                      setRerankMetrics(null);
                      setRetrievalCacheId("");
                    }}
                    type="button"
                  >
                    <strong>{String(cache.metadata_json.collection_name ?? cache.cache_key)}</strong>
                    <span>{cache.status}</span>
                    <span>{String(cache.metadata_json.index_mode ?? "dense")}</span>
                    <span>{embeddingModelName(cache)}</span>
                    {cache.metadata_json.error_json ? (
                      <small>{errorMessage(cache.metadata_json.error_json)}</small>
                    ) : null}
                  </button>
                ))}
              </div>
            )}
            {selectedIndexCache ? (
              <button className="text-action danger" onClick={handleDeleteSelectedIndexCache} type="button">
                Delete selected index
              </button>
            ) : null}
          </div>

          <form className="parameter-section" onSubmit={handleSaveRetrievalPreset}>
            <h2>Save Retrieval ParameterSet</h2>
            <label>
              Name
              <input value={retrievalPresetName} onChange={(event) => setRetrievalPresetName(event.target.value)} required />
            </label>
            <label>
              Description
              <input value={retrievalPresetDescription} onChange={(event) => setRetrievalPresetDescription(event.target.value)} />
            </label>
            <button className="secondary-action" disabled={isSavingRetrievalPreset} type="submit">
              {isSavingRetrievalPreset ? "Saving..." : "Save Retrieval ParameterSet"}
            </button>
          </form>

          <div className="parameter-section">
            <h2>Saved Retrieval ParameterSets</h2>
            {retrievalParameterSets.length === 0 ? (
              <div className="nested-empty">No retrieval ParameterSets saved yet.</div>
            ) : (
              <div className="index-cache-list">
                {retrievalParameterSets.map((parameterSet) => (
                  <button
                    className={parameterSet.id === selectedRetrievalParameterSetId ? "cache-item selected" : "cache-item"}
                    key={parameterSet.id}
                    onClick={() => handleApplyRetrievalPreset(parameterSet)}
                    type="button"
                  >
                    <strong>{parameterSet.name}</strong>
                    <span>{retrievalParameterSetLabel(parameterSet)}</span>
                    <small>{parameterSet.params_hash.slice(0, 18)}</small>
                  </button>
                ))}
              </div>
            )}
            {selectedRetrievalParameterSetId ? (
              <button className="text-action danger" onClick={handleDeleteSelectedRetrievalPreset} type="button">
                Delete selected ParameterSet
              </button>
            ) : null}
          </div>
        </div>

        <div className="stage-right">
          <div className="parameter-section">
            <h2>Retrieval Preview</h2>
            {selectedIndexCache ? (
              <>
                <div className="asset-mini-summary">
                  <span>{String(selectedIndexCache.metadata_json.collection_name)}</span>
                  <span>{selectedIndexCache.status}</span>
                  <span>{String(selectedIndexCache.metadata_json.index_mode ?? "dense")}</span>
                  <span>{String(selectedIndexCache.metadata_json.chunk_count ?? 0)} chunks</span>
                </div>
                {selectedIndexCache.status === "failed" ? (
                  <div className="notice">
                    Last indexing error: {errorMessage(selectedIndexCache.metadata_json.error_json)}
                  </div>
                ) : null}
                <div className="gt-question-panel">
                  <h3>Query Source</h3>
                  <div className="parameter-grid">
                    <label>
                      Question source
                      <select
                        value={questionSource}
                        onChange={(event) => {
                          setQuestionSource(event.target.value as typeof questionSource);
                          setRetrievalMetrics(null);
                          setRerankMetrics(null);
                        }}
                      >
                        <option value="manual">Manual</option>
                        <option value="ground_truth">Ground Truth</option>
                      </select>
                    </label>
                    {questionSource === "ground_truth" ? (
                      <>
                        <label>
                          Ground truth set
                          <select
                            value={selectedGroundTruthSetId}
                            onChange={(event) => {
                              setSelectedGroundTruthSetId(event.target.value);
                              setSelectedGroundTruthQuestionId("");
                              setRetrievalMetrics(null);
                              setRerankMetrics(null);
                            }}
                          >
                            {groundTruthSets.length === 0 ? <option value="">No GT sets</option> : null}
                            {groundTruthSets.map((groundTruthSet) => (
                              <option key={groundTruthSet.id} value={groundTruthSet.id}>
                                {groundTruthSet.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="wide-field">
                          Question
                          <select
                            value={selectedGroundTruthQuestionId}
                            onChange={(event) => {
                              setSelectedGroundTruthQuestionId(event.target.value);
                              setRetrievalResult(null);
                              setRerankResult(null);
                              setRetrievalMetrics(null);
                              setRerankMetrics(null);
                            }}
                          >
                            {groundTruthQuestions.length === 0 ? <option value="">No questions</option> : null}
                            {groundTruthQuestions.map((question) => (
                              <option key={question.question_id} value={question.question_id}>
                                {formatQuestionOption(question.question)}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="wide-field">
                          Selected question text
                          <textarea readOnly rows={3} value={query} />
                        </label>
                      </>
                    ) : (
                      <label className="wide-field">
                        Manual question
                        <textarea
                          rows={3}
                          value={query}
                          onChange={(event) => {
                            setQuery(event.target.value);
                            setRetrievalMetrics(null);
                            setRerankMetrics(null);
                          }}
                        />
                      </label>
                    )}
                  </div>
                </div>
                <div className="parameter-grid">
                  <label>
                    Strategy
                    <select
                      value={retrievalStrategy}
                      onChange={(event) => {
                        setRetrievalStrategy(event.target.value as typeof retrievalStrategy);
                        setSelectedRetrievalParameterSetId("");
                        setRetrievalMetrics(null);
                        setRerankMetrics(null);
                      }}
                    >
                      <option value="chunk_retrieval">chunk retrieval</option>
                      <option value="parent_page_retrieval">parent page retrieval</option>
                      <option value="parent_chapter_retrieval">parent chapter retrieval</option>
                    </select>
                  </label>
                  <label>
                    Mode
                    <select
                      value={retrievalMode}
                      onChange={(event) => {
                        setRetrievalMode(event.target.value as typeof retrievalMode);
                        setSelectedRetrievalParameterSetId("");
                        setRetrievalMetrics(null);
                        setRerankMetrics(null);
                      }}
                    >
                      <option value="hybrid">hybrid</option>
                      <option value="dense">dense</option>
                      <option value="sparse">sparse</option>
                    </select>
                  </label>
                  <label>
                    Parent Score
                    <select
                      disabled={retrievalStrategy === "chunk_retrieval"}
                      value={parentScore}
                      onChange={(event) => {
                        setParentScore(event.target.value as typeof parentScore);
                        setSelectedRetrievalParameterSetId("");
                        setRetrievalMetrics(null);
                        setRerankMetrics(null);
                      }}
                    >
                      <option value="max">max</option>
                      <option value="mean">mean</option>
                      <option value="sum">sum</option>
                    </select>
                  </label>
                  <label>
                    Top K
                    <input
                      max={50}
                      min={1}
                      type="number"
                      value={topK}
                      onChange={(event) => {
                        setTopK(Number(event.target.value));
                        setSelectedRetrievalParameterSetId("");
                        setRetrievalMetrics(null);
                        setRerankMetrics(null);
                      }}
                    />
                  </label>
                  <label>
                    Candidate K
                    <input
                      max={100}
                      min={topK}
                      type="number"
                      value={candidateK}
                      onChange={(event) => {
                        setCandidateK(Number(event.target.value));
                        setSelectedRetrievalParameterSetId("");
                        setRetrievalMetrics(null);
                        setRerankMetrics(null);
                      }}
                    />
                  </label>
                </div>
                <button
                  className="secondary-action"
                  disabled={isRetrieving || isReranking || selectedIndexCache.status !== "ready"}
                  onClick={handleRetrieve}
                  type="button"
                >
                  {isRetrieving ? "Retrieving..." : "Retrieve"}
                </button>
                {retrievalCacheId ? <div className="nested-empty">Retrieval cache: {retrievalCacheId}</div> : null}
                {questionSource === "ground_truth" && selectedGroundTruthQuestion ? (
                  <>
                    <GroundTruthPagesSummary question={selectedGroundTruthQuestion} />
                    <GroundTruthAnswerSummary question={selectedGroundTruthQuestion} />
                  </>
                ) : null}
                {retrievalMetrics ? <RankingMetrics score={retrievalMetrics} title="Retrieval Metrics" /> : null}
                {retrievalResult ? <RetrievalResult retrieval={retrievalResult} title="Retrieved Chunks" /> : null}
              </>
            ) : (
              <div className="nested-empty">Create a Qdrant index before retrieval preview.</div>
            )}
          </div>

          <div className="parameter-section">
            <h2>Reranking Preview</h2>
            {selectedRerankerModel ? (
              <>
                <div className="parameter-grid">
                  <label>
                    Reranker
                    <select
                      value={rerankerModelId}
                      onChange={(event) => {
                        setRerankerModelId(event.target.value);
                        setSelectedRetrievalParameterSetId("");
                      }}
                    >
                      {rerankerModels.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="asset-mini-summary">
                  <span>{selectedRerankerModel.provider}</span>
                  <span>{selectedRerankerModel.model_name}</span>
                  <span>{selectedRerankerModel.backend}</span>
                </div>
                <RerankRequestSummary
                  candidateCount={rerankCandidateCount}
                  model={selectedRerankerModel}
                  topK={topK}
                />
                <div className="parameter-grid">
                  {selectedRerankerModel.fields.map((field) => (
                    <EmbeddingFieldControl
                      field={field}
                      key={field.name}
                      value={rerankerParams[field.name] ?? field.default}
                      onChange={(value) =>
                        setRerankerParams((current) => {
                          setSelectedRetrievalParameterSetId("");
                          return { ...current, [field.name]: value };
                        })
                      }
                    />
                  ))}
                </div>
                <p className="form-note">{selectedRerankerModel.description}</p>
                <button
                  className="secondary-action"
                  disabled={isRetrieving || isReranking || !retrievalCacheId}
                  onClick={handleRerank}
                  type="button"
                >
                  {isReranking ? "Reranking..." : "Rerank current candidates"}
                </button>
              </>
            ) : (
              <div className="nested-empty">No reranker models are available.</div>
            )}
            {!retrievalCacheId ? (
              <div className="nested-empty">Run retrieval first, then rerank the current candidate cache.</div>
            ) : null}
            {rerankMetrics ? <RankingMetrics score={rerankMetrics} title="Reranking Metrics" /> : null}
            {rerankResult ? <RetrievalResult retrieval={rerankResult} title="Reranked Chunks" /> : null}
          </div>

          <div className="parameter-section">
            <h2>Ground Truth Evaluation</h2>
            <div className="asset-mini-summary">
              <span>{groundTruthQuestions.length} questions</span>
              <span>{selectedIndexCache ? String(selectedIndexCache.metadata_json.collection_name ?? selectedIndexCache.cache_key) : "no index"}</span>
              <span>{retrievalStrategy}</span>
              <span>{retrievalMode}</span>
            </div>
            <label className="check-row">
              <input
                checked={evaluateWithReranking}
                disabled={!selectedRerankerModel}
                type="checkbox"
                onChange={(event) => setEvaluateWithReranking(event.target.checked)}
              />
              Use selected reranker
            </label>
            <button
              className="secondary-action"
              disabled={
                isEvaluating ||
                !selectedIndexCache ||
                selectedIndexCache.status !== "ready" ||
                !selectedGroundTruthSetId ||
                groundTruthQuestions.length === 0
              }
              onClick={handleEvaluateGroundTruth}
              type="button"
            >
              {isEvaluating ? "Evaluating..." : "Run GT evaluation"}
            </button>
            {evaluationExperiment ? <EvaluationResult experiment={evaluationExperiment} /> : null}
          </div>

          <div className="parameter-section">
            <h2>Index Snapshot</h2>
            <pre className="json-preview">
              {JSON.stringify(selectedIndexCache?.metadata_json ?? { chunks_cache_id: chunksCacheId || null }, null, 2)}
            </pre>
          </div>

          <div className="parameter-section">
            <h2>Retrieval Snapshot</h2>
            <pre className="json-preview">{JSON.stringify(retrievalSnapshot, null, 2)}</pre>
          </div>

          <div className="parameter-section">
            <h2>Selected Chunks Cache</h2>
            {selectedChunksCache ? (
              <pre className="json-preview">{JSON.stringify(selectedChunksCache.metadata_json, null, 2)}</pre>
            ) : (
              <div className="nested-empty">Select materialized chunks first.</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function EmbeddingFieldControl({
  field,
  onChange,
  value,
}: {
  field: EmbeddingModel["fields"][number];
  onChange: (value: EmbeddingParamValue) => void;
  value: EmbeddingParamValue;
}) {
  if (field.type === "boolean") {
    return (
      <label className="check-row" title={field.help_text ?? undefined}>
        <input checked={Boolean(value)} type="checkbox" onChange={(event) => onChange(event.target.checked)} />
        {field.label}
      </label>
    );
  }

  if (field.type === "select") {
    return (
      <label title={field.help_text ?? undefined}>
        {field.label}
        <select value={String(value)} onChange={(event) => onChange(event.target.value)}>
          {(field.options ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (field.type === "number") {
    return (
      <label title={field.help_text ?? undefined}>
        {field.label}
        <input
          max={field.max ?? undefined}
          min={field.min ?? undefined}
          step={field.step ?? undefined}
          type="number"
          value={Number(value)}
          onChange={(event) => onChange(Number(event.target.value))}
        />
      </label>
    );
  }

  return (
    <label title={field.help_text ?? undefined}>
      {field.label}
      <input value={String(value)} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function RetrievalResult({ retrieval, title }: { retrieval: RetrievalPreviewResponse; title: string }) {
  return (
    <div className="chunk-list">
      <h3>{title}</h3>
      {retrieval.retrieved_chunks.map((chunk, index) => (
        <ChunkResultItem chunk={chunk} index={index} key={`${chunk.chunk_id ?? "chunk"}-${index}`} />
      ))}
    </div>
  );
}

function RerankRequestSummary({
  candidateCount,
  model,
  topK,
}: {
  candidateCount: number;
  model: RerankerModel;
  topK: number;
}) {
  const isRemote = model.backend === "remote_api" || model.provider === "voyage";
  return (
    <div className="chunk-preview">
      <div className="asset-mini-summary">
        <span>{candidateCount > 0 ? `${formatInteger(candidateCount)} candidate chunks` : "no candidate cache"}</span>
        <span>{formatInteger(topK)} final chunks</span>
        {isRemote ? <span>query + candidate text to remote API</span> : <span>local scoring</span>}
      </div>
    </div>
  );
}

function ChunkResultItem({
  chunk,
  index,
}: {
  chunk: RetrievalPreviewResponse["retrieved_chunks"][number];
  index: number;
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <details
      className="chunk-card chunk-card-collapsible"
      onToggle={(event) => setIsOpen(event.currentTarget.open)}
    >
      <summary className="chunk-summary">
        <span className="chunk-summary-main">{chunkResultLabel(chunk, index)}</span>
        <span className="chunk-summary-score">{primaryScoreLabel(chunk)}</span>
      </summary>
      {isOpen ? (
        <div className="chunk-card-body">
          <div className="chunk-meta">
            {chunk.chunk_id ? <strong>{chunk.chunk_id}</strong> : null}
            {chunk.source_name ? <span>{chunk.source_name}</span> : null}
            {pageLabel(chunk) ? <span>{pageLabel(chunk)}</span> : null}
            {chunk.token_count ? <span>{chunk.token_count} tokens</span> : null}
            {chunk.score !== undefined && chunk.score !== null ? <span>score {chunk.score.toFixed(4)}</span> : null}
            {chunk.dense_score !== undefined && chunk.dense_score !== null ? (
              <span>dense {chunk.dense_score.toFixed(4)}</span>
            ) : null}
            {chunk.sparse_score !== undefined && chunk.sparse_score !== null ? (
              <span>sparse {chunk.sparse_score.toFixed(4)}</span>
            ) : null}
            {chunk.rerank_score !== undefined && chunk.rerank_score !== null ? (
              <span>rerank {chunk.rerank_score.toFixed(4)}</span>
            ) : null}
            {chunk.original_score !== undefined && chunk.original_score !== null ? (
              <span>original {chunk.original_score.toFixed(4)}</span>
            ) : null}
            {chunk.original_rank ? <span>rank {chunk.original_rank}</span> : null}
          </div>
          {chunk.heading_path && chunk.heading_path.length > 0 ? (
            <div className="chunk-heading-path">{chunk.heading_path.join(" / ")}</div>
          ) : null}
          {chunk.text_preview ? <pre>{chunk.text_preview}</pre> : null}
        </div>
      ) : null}
    </details>
  );
}

function GroundTruthPagesSummary({ question }: { question: GroundTruthQuestion }) {
  const pages = formatRelevantPages(question);
  if (pages.length === 0) {
    return null;
  }
  return (
    <div className="chunk-preview">
      <h3>Ground Truth Pages</h3>
      <div className="asset-mini-summary">
        {pages.map((page, index) => (
          <span key={`${page}-${index}`}>{page}</span>
        ))}
      </div>
    </div>
  );
}

function GroundTruthAnswerSummary({ question }: { question: GroundTruthQuestion }) {
  const answer = groundTruthAnswerText(question);
  if (!answer) {
    return null;
  }
  return (
    <div className="chunk-preview">
      <h3>Ground Truth Answer</h3>
      <pre className="ground-truth-answer">{answer}</pre>
    </div>
  );
}

function chunkResultLabel(chunk: RetrievalPreviewResponse["retrieved_chunks"][number], index: number): string {
  return [
    chunk.source_name || `result ${index + 1}`,
    pageLabel(chunk),
    chunk.token_count ? `${chunk.token_count} tokens` : "",
  ]
    .filter(Boolean)
    .join(" / ");
}

function pageLabel(chunk: RetrievalPreviewResponse["retrieved_chunks"][number]): string {
  const pageStart = typeof chunk.page_start === "number" ? chunk.page_start : undefined;
  const pageEnd = typeof chunk.page_end === "number" ? chunk.page_end : undefined;
  const page = typeof chunk.page === "number" ? chunk.page : undefined;
  if (pageStart !== undefined || pageEnd !== undefined) {
    const start = pageStart ?? page ?? pageEnd;
    const end = pageEnd ?? pageStart;
    if (start !== undefined && end !== undefined && end !== start) {
      return `pages ${start}-${end}`;
    }
    return start !== undefined ? `page ${start}` : "";
  }
  return page !== undefined ? `page ${page}` : "";
}

function primaryScoreLabel(chunk: RetrievalPreviewResponse["retrieved_chunks"][number]): string {
  if (chunk.rerank_score !== undefined && chunk.rerank_score !== null) {
    return `rerank ${chunk.rerank_score.toFixed(4)}`;
  }
  if (chunk.score !== undefined && chunk.score !== null) {
    return `score ${chunk.score.toFixed(4)}`;
  }
  if (chunk.dense_score !== undefined && chunk.dense_score !== null) {
    return `dense ${chunk.dense_score.toFixed(4)}`;
  }
  if (chunk.sparse_score !== undefined && chunk.sparse_score !== null) {
    return `sparse ${chunk.sparse_score.toFixed(4)}`;
  }
  return "score n/a";
}

function groundTruthAnswerText(question: GroundTruthQuestion): string {
  if (question.expected_answer_brief && question.expected_answer_brief.trim()) {
    return question.expected_answer_brief.trim();
  }
  if (question.expected_answer !== undefined && question.expected_answer !== null) {
    return typeof question.expected_answer === "string"
      ? question.expected_answer
      : JSON.stringify(question.expected_answer, null, 2);
  }
  return "";
}

function RankingMetrics({ score, title }: { score: GroundTruthRankingScore; title: string }) {
  return (
    <div className="chunk-preview">
      <h3>{title}</h3>
      <div className="metric-strip retrieval-metrics-strip">
        {Object.entries(score.metrics).map(([name, value]) => (
          <div key={name}>
            <span>{formatMetricName(name)}</span>
            <strong>{formatMetricValue(value)}</strong>
          </div>
        ))}
      </div>
      {score.warnings.length > 0 ? (
        <div className="warning-list">
          {score.warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function EvaluationResult({ experiment }: { experiment: SavedExperiment }) {
  const summary = experiment.metrics_summary_json as {
    evaluation?: Record<string, unknown>;
    metric_averages?: Record<string, unknown>;
    questions?: Array<Record<string, unknown>>;
  };
  const evaluation = summary.evaluation ?? {};
  const metricAverages = summary.metric_averages ?? {};
  const questions = summary.questions ?? [];
  return (
    <div className="chunk-preview">
      <h3>Evaluation Result</h3>
      <div className="asset-mini-summary">
        <span>{experiment.status}</span>
        <span>{String(evaluation.completed_question_count ?? 0)} completed</span>
        <span>{String(evaluation.error_count ?? 0)} errors</span>
        <span>{String(evaluation.warning_count ?? 0)} warnings</span>
      </div>
      {Object.keys(metricAverages).length > 0 ? (
        <div className="metric-strip retrieval-metrics-strip">
          {Object.entries(metricAverages).map(([name, value]) => (
            <div key={name}>
              <span>{formatMetricName(name)}</span>
              <strong>{typeof value === "number" ? formatMetricValue(value) : "-"}</strong>
            </div>
          ))}
        </div>
      ) : null}
      {questions.length > 0 ? (
        <div className="table">
          <div className="table-row experiment-table table-head">
            <span>Question</span>
            <span>Status</span>
            <span>Top result</span>
            <span>Hit</span>
            <span>Warnings</span>
          </div>
          {questions.map((question, index) => (
            <div className="table-row experiment-table" key={String(question.question_id ?? index)}>
              <span>{formatQuestionOption(String(question.question ?? question.question_id ?? ""))}</span>
              <span>{String(question.status ?? "")}</span>
              <span>{formatEvaluationTopResult(question.top_result)}</span>
              <span>{formatEvaluationHit(question.metrics)}</span>
              <span>{Array.isArray(question.warnings) ? question.warnings.length : 0}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function upsertCache(caches: DerivedCache[], cache: DerivedCache): DerivedCache[] {
  const next = caches.filter((item) => item.id !== cache.id);
  return [cache, ...next];
}

function ChunksCacheSummary({ assets, cache }: { assets: DataAsset[]; cache: DerivedCache }) {
  return (
    <div className="asset-mini-summary">
      <span>{cacheLabel(cache, assets)}</span>
      <span>{cache.status}</span>
      <span>{cacheChunkCount(cache)} chunks</span>
      <span>{cacheChunkingStrategy(cache)}</span>
      <span>{cache.params_hash.slice(0, 18)}</span>
    </div>
  );
}

function cacheLabel(cache: DerivedCache, assets: DataAsset[]): string {
  const asset = assets.find((item) => item.id === cache.data_asset_id);
  const strategy = cacheChunkingStrategy(cache);
  return asset ? `${asset.name} / ${strategy}` : `${cache.cache_key} / ${strategy}`;
}

function cacheChunkingStrategy(cache: DerivedCache): string {
  const chunking = cache.metadata_json.chunking;
  if (chunking && typeof chunking === "object" && typeof (chunking as { strategy?: unknown }).strategy === "string") {
    return (chunking as { strategy: string }).strategy;
  }
  return "chunks";
}

function cacheChunkCount(cache: DerivedCache): number {
  const summary = cache.metadata_json.summary;
  if (summary && typeof summary === "object" && typeof (summary as { chunk_count?: unknown }).chunk_count === "number") {
    return (summary as { chunk_count: number }).chunk_count;
  }
  return typeof cache.metadata_json.chunk_count === "number" ? cache.metadata_json.chunk_count : 0;
}

function cacheIndexingEstimate(cache: DerivedCache): { chunkCount: number; estimatedTokens: number | null } {
  const chunkCount = cacheChunkCount(cache);
  const summary = cache.metadata_json.summary;
  if (summary && typeof summary === "object") {
    const avgTokens = (summary as { avg_tokens?: unknown }).avg_tokens;
    if (typeof avgTokens === "number" && Number.isFinite(avgTokens)) {
      return {
        chunkCount,
        estimatedTokens: Math.round(chunkCount * avgTokens),
      };
    }
  }
  return { chunkCount, estimatedTokens: null };
}

function cacheBelongsToChunks(indexCache: DerivedCache, chunksCache: DerivedCache): boolean {
  return (
    String(indexCache.metadata_json.chunks_cache_id ?? "") === chunksCache.id ||
    String(indexCache.metadata_json.chunks_cache_key ?? "") === chunksCache.cache_key
  );
}

function retrievalParameterSetLabel(parameterSet: ParameterSet): string {
  const retrieval = parameterSet.params_json.retrieval;
  if (isRetrievalParams(retrieval)) {
    return `${retrieval.strategy} / ${retrieval.mode}`;
  }
  return "retrieval";
}

function isRetrievalParams(value: unknown): value is {
  candidate_k: number;
  mode: "dense" | "sparse" | "hybrid";
  parent_score: "max" | "mean" | "sum";
  strategy: "chunk_retrieval" | "parent_page_retrieval" | "parent_chapter_retrieval";
  top_k: number;
} {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.candidate_k === "number" &&
    typeof candidate.mode === "string" &&
    typeof candidate.parent_score === "string" &&
    typeof candidate.strategy === "string" &&
    typeof candidate.top_k === "number"
  );
}

function isRerankingParams(value: unknown): value is {
  model_id: string;
  params: Record<string, EmbeddingParamValue>;
} {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as { model_id?: unknown; params?: unknown };
  return typeof candidate.model_id === "string" && Boolean(candidate.params) && typeof candidate.params === "object";
}

function effectiveEmbeddingDims(
  model: EmbeddingModel,
  params: Record<string, EmbeddingParamValue>,
): number {
  const outputDimension = params.output_dimension;
  if (typeof outputDimension === "number" && Number.isFinite(outputDimension)) {
    return outputDimension;
  }
  if (typeof outputDimension === "string") {
    const parsed = Number(outputDimension);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return model.vector_size;
}

async function sha256Hex(input: string): Promise<string> {
  const encoded = new TextEncoder().encode(input);
  const digest = await window.crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function stableStringify(value: unknown): string {
  return JSON.stringify(sortJson(value));
}

function sortJson(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortJson);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, sortJson(item)]),
    );
  }
  return value;
}

function embeddingModelName(cache: DerivedCache): string {
  const embedding = cache.metadata_json.embedding;
  if (embedding && typeof embedding === "object" && "model" in embedding) {
    return String((embedding as { model?: unknown }).model ?? "");
  }
  return "";
}

function errorMessage(value: unknown): string {
  if (value && typeof value === "object" && "message" in value) {
    return String((value as { message?: unknown }).message ?? "Unknown error");
  }
  return "Unknown error";
}

function formatMetricName(name: string): string {
  return name.replace(/_/g, " ");
}

function formatMetricValue(value: number): string {
  if (!Number.isFinite(value)) {
    return "-";
  }
  if (Number.isInteger(value) && Math.abs(value) >= 10) {
    return String(value);
  }
  return value.toFixed(3);
}

function formatEvaluationHit(value: unknown): string {
  if (!value || typeof value !== "object") {
    return "-";
  }
  const metrics = value as Record<string, unknown>;
  const hit = metrics.hit_at_k ?? metrics.page_hit_at_k ?? metrics.expected_not_found;
  return typeof hit === "number" ? formatMetricValue(hit) : "-";
}

function formatEvaluationTopResult(value: unknown): string {
  if (!value || typeof value !== "object") {
    return "-";
  }
  const result = value as Record<string, unknown>;
  const parts = [
    result.source_name ? String(result.source_name) : "",
    typeof result.page === "number" ? `page ${result.page}` : "",
    typeof result.page_start === "number" ? `page ${result.page_start}` : "",
    result.chunk_id ? String(result.chunk_id) : "",
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" / ") : "-";
}

function formatInteger(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

function formatEstimatedTokens(value: number | null): string {
  if (value === null) {
    return "estimated tokens unknown";
  }
  return `~${formatInteger(value)} estimated tokens`;
}

function formatQuestionOption(question: string): string {
  const normalized = question.replace(/\s+/g, " ").trim();
  return normalized.length > 96 ? `${normalized.slice(0, 93)}...` : normalized;
}

function formatRelevantPages(question: GroundTruthQuestion): string[] {
  return (question.relevant_pages ?? [])
    .map((reference) => {
      const pageIndex = reference.page_index;
      if (typeof pageIndex !== "number") {
        return "";
      }
      return `page ${pageIndex + 1} / index ${pageIndex}`;
    })
    .filter(Boolean);
}
