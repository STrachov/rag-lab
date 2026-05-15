import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  ChunkingParams,
  createQdrantIndex,
  DataAsset,
  DerivedCache,
  EmbeddingModel,
  EmbeddingParamValue,
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
  materializeChunks,
  ParameterSet,
  previewRerank,
  previewRetrieval,
  Project,
  RerankerModel,
  RetrievalPreviewResponse,
  scoreGroundTruthRanking,
  SparseModel,
} from "../api/client";

type IndexingPageProps = {
  currentProject: Project | null;
};

const DEFAULT_CHUNKING: ChunkingParams = {
  params: {
    chunk_overlap: 120,
    chunk_size: 900,
    page_boundary_mode: "soft",
    preserve_headings: true,
    preserve_tables: true,
    tokenizer: "cl100k_base",
  },
  strategy: "heading_recursive",
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
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [selectedParameterSetId, setSelectedParameterSetId] = useState("");
  const [chunksCacheId, setChunksCacheId] = useState(searchParams.get("chunks_cache_id") ?? "");
  const [indexCaches, setIndexCaches] = useState<DerivedCache[]>([]);
  const [selectedIndexCacheId, setSelectedIndexCacheId] = useState("");
  const [embeddingModelId, setEmbeddingModelId] = useState("intfloat_multilingual_e5_small");
  const [embeddingParams, setEmbeddingParams] = useState<Record<string, EmbeddingParamValue>>({});
  const [sparseModelId, setSparseModelId] = useState("bm25_local");
  const [sparseParams, setSparseParams] = useState<Record<string, EmbeddingParamValue>>({});
  const [indexMode, setIndexMode] = useState<"dense" | "sparse" | "hybrid">("hybrid");
  const [retrievalMode, setRetrievalMode] = useState<"dense" | "sparse" | "hybrid">("hybrid");
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
  const [isMaterializing, setIsMaterializing] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [isRetrieving, setIsRetrieving] = useState(false);
  const [isReranking, setIsReranking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const preparedAssets = useMemo(
    () => dataAssets.filter((asset) => asset.asset_type === "prepared"),
    [dataAssets],
  );
  const chunkingParameterSets = useMemo(
    () => parameterSets.filter((set) => set.category === "chunking"),
    [parameterSets],
  );
  const selectedModel = embeddingModels.find((model) => model.id === embeddingModelId);
  const selectedSparseModel = sparseModels.find((model) => model.id === sparseModelId);
  const selectedRerankerModel = rerankerModels.find((model) => model.id === rerankerModelId);
  const selectedParameterSet = chunkingParameterSets.find((set) => set.id === selectedParameterSetId);
  const selectedIndexCache = indexCaches.find((cache) => cache.id === selectedIndexCacheId) ?? null;

  useEffect(() => {
    if (!currentProject) {
      setDataAssets([]);
      setParameterSets([]);
      setEmbeddingModels([]);
      setSparseModels([]);
      setRerankerModels([]);
      setGroundTruthSets([]);
      setGroundTruthQuestions([]);
      return;
    }

    Promise.all([
      listDataAssets(currentProject.id),
      listDerivedCaches(currentProject.id, "qdrant_index"),
      listParameterSets(currentProject.id),
      listEmbeddingModels(currentProject.id),
      listSparseModels(currentProject.id),
      listRerankerModels(currentProject.id),
      listGroundTruthSets(currentProject.id),
    ])
      .then(([assetResult, cacheResult, parameterResult, modelResult, sparseResult, rerankerResult, groundTruthResult]) => {
        setDataAssets(assetResult.data_assets);
        setIndexCaches(cacheResult.derived_caches);
        setParameterSets(parameterResult.parameter_sets);
        setEmbeddingModels(modelResult.models);
        setSparseModels(sparseResult.models);
        setRerankerModels(rerankerResult.models);
        setGroundTruthSets(groundTruthResult.ground_truth_sets);
        setSelectedGroundTruthSetId((current) => current || groundTruthResult.ground_truth_sets[0]?.id || "");
        setSelectedAssetId((current) => current || firstPreparedId(assetResult.data_assets));
        const firstChunkingSet = parameterResult.parameter_sets.find((set) => set.category === "chunking");
        setSelectedParameterSetId((current) => current || firstChunkingSet?.id || "");
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
        const firstReadyIndex = cacheResult.derived_caches.find((cache) => cache.status === "ready");
        setSelectedIndexCacheId((current) => current || firstReadyIndex?.id || cacheResult.derived_caches[0]?.id || "");
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [currentProject]);

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

  async function handleMaterialize() {
    if (!currentProject || !selectedAssetId) {
      return;
    }
    const chunking = chunkingFromParameterSet(selectedParameterSet);
    setIsMaterializing(true);
    try {
      const cache = await materializeChunks(currentProject.id, {
        chunking,
        data_asset_id: selectedAssetId,
      });
      setChunksCacheId(cache.id);
      setSearchParams({ chunks_cache_id: cache.id });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to materialize chunks");
    } finally {
      setIsMaterializing(false);
    }
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
        query: query.trim(),
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

      <div className="parameter-workbench">
        <div className="chunking-form">
          <div className="parameter-section">
            <h2>Chunks</h2>
            <div className="parameter-grid">
              <label>
                Prepared data asset
                <select value={selectedAssetId} onChange={(event) => setSelectedAssetId(event.target.value)}>
                  {preparedAssets.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Chunking ParameterSet
                <select
                  value={selectedParameterSetId}
                  onChange={(event) => setSelectedParameterSetId(event.target.value)}
                >
                  <option value="">Default heading recursive</option>
                  {chunkingParameterSets.map((set) => (
                    <option key={set.id} value={set.id}>
                      {set.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <button
              className="secondary-action"
              disabled={isMaterializing || !selectedAssetId}
              onClick={handleMaterialize}
              type="button"
            >
              {isMaterializing ? "Materializing..." : "Materialize chunks"}
            </button>
            {chunksCacheId ? <div className="nested-empty">Chunks cache: {chunksCacheId}</div> : null}
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
                  <span>{selectedModel.vector_size} dims</span>
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
            <button className="primary-action" disabled={isIndexing || !chunksCacheId} type="submit">
              {isIndexing ? "Indexing..." : "Create Qdrant index"}
            </button>
          </form>

          <div className="parameter-section">
            <h2>Existing Indexes</h2>
            {indexCaches.length === 0 ? (
              <div className="nested-empty">No Qdrant index caches for this project yet.</div>
            ) : (
              <div className="index-cache-list">
                {indexCaches.map((cache) => (
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
          </div>
        </div>

        <div className="chunk-preview-panel">
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
                  <h3>Ground Truth Metrics</h3>
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
                      <label>
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
                              {question.question_id}: {question.question}
                            </option>
                          ))}
                        </select>
                      </label>
                      </>
                    ) : (
                      <div className="form-note">Manual queries run without GT metrics.</div>
                    )}
                  </div>
                </div>
                <div className="parameter-grid">
                  <label>
                    Mode
                    <select
                      value={retrievalMode}
                      onChange={(event) => {
                        setRetrievalMode(event.target.value as typeof retrievalMode);
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
                    Query
                    <input
                      readOnly={questionSource === "ground_truth"}
                      value={query}
                      onChange={(event) => {
                        setQuery(event.target.value);
                        setRetrievalMetrics(null);
                        setRerankMetrics(null);
                      }}
                    />
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
                      onChange={(event) => setRerankerModelId(event.target.value)}
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
                <div className="parameter-grid">
                  {selectedRerankerModel.fields.map((field) => (
                    <EmbeddingFieldControl
                      field={field}
                      key={field.name}
                      value={rerankerParams[field.name] ?? field.default}
                      onChange={(value) =>
                        setRerankerParams((current) => ({ ...current, [field.name]: value }))
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
            <h2>Index Snapshot</h2>
            <pre className="json-preview">
              {JSON.stringify(selectedIndexCache?.metadata_json ?? { chunks_cache_id: chunksCacheId || null }, null, 2)}
            </pre>
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
        <article className="chunk-card" key={`${chunk.chunk_id ?? "chunk"}-${index}`}>
          <div className="chunk-meta">
            <strong>{chunk.chunk_id}</strong>
            {chunk.score !== undefined && chunk.score !== null ? <span>{chunk.score.toFixed(4)}</span> : null}
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
            {chunk.source_name ? <span>{chunk.source_name}</span> : null}
            {chunk.token_count ? <span>{chunk.token_count} tokens</span> : null}
          </div>
          {chunk.heading_path && chunk.heading_path.length > 0 ? (
            <div className="chunk-heading-path">{chunk.heading_path.join(" / ")}</div>
          ) : null}
          {chunk.text_preview ? <pre>{chunk.text_preview}</pre> : null}
        </article>
      ))}
    </div>
  );
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

function firstPreparedId(dataAssets: DataAsset[]): string {
  return dataAssets.find((asset) => asset.asset_type === "prepared")?.id ?? "";
}

function chunkingFromParameterSet(parameterSet?: ParameterSet): ChunkingParams {
  const maybeChunking = parameterSet?.params_json?.chunking;
  if (isChunkingParams(maybeChunking)) {
    return maybeChunking;
  }
  return DEFAULT_CHUNKING;
}

function isChunkingParams(value: unknown): value is ChunkingParams {
  return Boolean(
    value &&
      typeof value === "object" &&
      typeof (value as ChunkingParams).strategy === "string" &&
      typeof (value as ChunkingParams).params === "object",
  );
}

function upsertCache(caches: DerivedCache[], cache: DerivedCache): DerivedCache[] {
  const next = caches.filter((item) => item.id !== cache.id);
  return [cache, ...next];
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
