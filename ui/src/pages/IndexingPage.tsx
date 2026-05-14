import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  ChunkingParams,
  createQdrantIndex,
  DataAsset,
  DerivedCache,
  EmbeddingModel,
  EmbeddingParamValue,
  listDataAssets,
  listDerivedCaches,
  listEmbeddingModels,
  listParameterSets,
  listSparseModels,
  materializeChunks,
  ParameterSet,
  previewRetrieval,
  Project,
  RetrievalPreviewResponse,
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
  const [query, setQuery] = useState("Where from is Wayne Xin Zhao?");
  const [topK, setTopK] = useState(5);
  const [retrieval, setRetrieval] = useState<RetrievalPreviewResponse | null>(null);
  const [isMaterializing, setIsMaterializing] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [isRetrieving, setIsRetrieving] = useState(false);
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
  const selectedParameterSet = chunkingParameterSets.find((set) => set.id === selectedParameterSetId);
  const selectedIndexCache = indexCaches.find((cache) => cache.id === selectedIndexCacheId) ?? null;

  useEffect(() => {
    if (!currentProject) {
      setDataAssets([]);
      setParameterSets([]);
      setEmbeddingModels([]);
      setSparseModels([]);
      return;
    }

    Promise.all([
      listDataAssets(currentProject.id),
      listDerivedCaches(currentProject.id, "qdrant_index"),
      listParameterSets(currentProject.id),
      listEmbeddingModels(currentProject.id),
      listSparseModels(currentProject.id),
    ])
      .then(([assetResult, cacheResult, parameterResult, modelResult, sparseResult]) => {
        setDataAssets(assetResult.data_assets);
        setIndexCaches(cacheResult.derived_caches);
        setParameterSets(parameterResult.parameter_sets);
        setEmbeddingModels(modelResult.models);
        setSparseModels(sparseResult.models);
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
        const firstReadyIndex = cacheResult.derived_caches.find((cache) => cache.status === "ready");
        setSelectedIndexCacheId((current) => current || firstReadyIndex?.id || cacheResult.derived_caches[0]?.id || "");
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [currentProject]);

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
      setRetrieval(null);
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
        index_cache_id: selectedIndexCache.id,
        mode: retrievalMode,
        query: query.trim(),
        top_k: topK,
      });
      setRetrieval(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to retrieve chunks");
    } finally {
      setIsRetrieving(false);
    }
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
          <p className="eyebrow">Indexing</p>
          <h1>Embedding & Qdrant</h1>
          <p>Select or create a project first. Index caches are scoped to the current project.</p>
        </header>
        <div className="empty-state">No project selected.</div>
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Indexing</p>
        <h1>Embedding & Qdrant</h1>
        <p>Materialize normalized chunks, embed them with a registered model, and create a Qdrant index cache.</p>
      </header>

      {error ? <div className="notice">Indexing unavailable: {error}</div> : null}

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
                      setRetrieval(null);
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
                <div className="parameter-grid">
                  <label>
                    Mode
                    <select value={retrievalMode} onChange={(event) => setRetrievalMode(event.target.value as typeof retrievalMode)}>
                      <option value="hybrid">hybrid</option>
                      <option value="dense">dense</option>
                      <option value="sparse">sparse</option>
                    </select>
                  </label>
                  <label>
                    Query
                    <input value={query} onChange={(event) => setQuery(event.target.value)} />
                  </label>
                  <label>
                    Top K
                    <input
                      max={50}
                      min={1}
                      type="number"
                      value={topK}
                      onChange={(event) => setTopK(Number(event.target.value))}
                    />
                  </label>
                </div>
                <button
                  className="secondary-action"
                  disabled={isRetrieving || selectedIndexCache.status !== "ready"}
                  onClick={handleRetrieve}
                  type="button"
                >
                  {isRetrieving ? "Retrieving..." : "Retrieve"}
                </button>
              </>
            ) : (
              <div className="nested-empty">Create a Qdrant index before retrieval preview.</div>
            )}
            {retrieval ? <RetrievalResult retrieval={retrieval} /> : null}
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

function RetrievalResult({ retrieval }: { retrieval: RetrievalPreviewResponse }) {
  return (
    <div className="chunk-list">
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
