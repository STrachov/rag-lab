import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  ChunkingParams,
  ChunkingParamValue,
  ChunkingPreviewResponse,
  ChunkingStrategy,
  createParameterSet,
  DataAsset,
  deleteDerivedCache,
  deleteParameterSet,
  DerivedCache,
  downloadGroundTruthAuthoringPack,
  listChunkingStrategies,
  listDataAssets,
  listDerivedCaches,
  listParameterSets,
  materializeChunks,
  ParameterSet,
  previewChunking,
  Project,
} from "../api/client";

type ParametersPageProps = {
  currentProject: Project | null;
};

const DEFAULT_CHUNKING: ChunkingParams = {
  params: {},
  strategy: "heading_recursive",
};

export function ParametersPage({ currentProject }: ParametersPageProps) {
  const [parameterSets, setParameterSets] = useState<ParameterSet[]>([]);
  const [dataAssets, setDataAssets] = useState<DataAsset[]>([]);
  const [strategies, setStrategies] = useState<ChunkingStrategy[]>([]);
  const [chunkCaches, setChunkCaches] = useState<DerivedCache[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isMaterializing, setIsMaterializing] = useState(false);
  const [isDownloadingPack, setIsDownloadingPack] = useState(false);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [selectedCacheId, setSelectedCacheId] = useState("");
  const [selectedParameterSetId, setSelectedParameterSetId] = useState("");
  const [name, setName] = useState("Chunking baseline");
  const [description, setDescription] = useState("");
  const [chunking, setChunking] = useState<ChunkingParams>(DEFAULT_CHUNKING);
  const [maxChunks, setMaxChunks] = useState(50);
  const [preview, setPreview] = useState<ChunkingPreviewResponse | null>(null);
  const navigate = useNavigate();

  const preparedAssets = useMemo(
    () => dataAssets.filter((asset) => asset.asset_type === "prepared"),
    [dataAssets],
  );
  const chunkingParameterSets = useMemo(
    () => parameterSets.filter((set) => set.category === "chunking"),
    [parameterSets],
  );
  const selectedAsset = preparedAssets.find((asset) => asset.id === selectedAssetId) ?? null;
  const selectedStrategy = strategies.find((strategy) => strategy.id === chunking.strategy) ?? null;
  const linkedChunkCaches = selectedAsset
    ? chunkCaches.filter((cache) => cache.data_asset_id === selectedAsset.id)
    : [];
  const selectedCache =
    linkedChunkCaches.find((cache) => cache.id === selectedCacheId) ?? linkedChunkCaches[0] ?? null;
  const snapshot = useMemo(() => ({ chunking }), [chunking]);
  const strategyWarning = selectedAsset && selectedStrategy
    ? parentUnitWarning(selectedAsset, selectedStrategy.id)
    : null;

  useEffect(() => {
    if (!currentProject) {
      setParameterSets([]);
      setDataAssets([]);
      setStrategies([]);
      setChunkCaches([]);
      setSelectedAssetId("");
      setSelectedCacheId("");
      setSelectedParameterSetId("");
      return;
    }

    Promise.all([
      listParameterSets(currentProject.id),
      listDataAssets(currentProject.id),
      listChunkingStrategies(currentProject.id),
      listDerivedCaches(currentProject.id, "chunks"),
    ])
      .then(([parameterResult, assetResult, strategyResult, cacheResult]) => {
        setParameterSets(parameterResult.parameter_sets);
        setDataAssets(assetResult.data_assets);
        setStrategies(strategyResult.strategies);
        setChunkCaches(cacheResult.derived_caches);
        const firstPrepared = assetResult.data_assets.find((asset) => asset.asset_type === "prepared");
        setSelectedAssetId((current) => current || firstPrepared?.id || "");
        const firstStrategy = strategyResult.strategies[0];
        if (firstStrategy) {
          setChunking((current) => {
            const currentStrategy = strategyResult.strategies.find((strategy) => strategy.id === current.strategy);
            return currentStrategy
              ? { strategy: current.strategy, params: mergeDefaults(currentStrategy, current.params) }
              : { strategy: firstStrategy.id, params: firstStrategy.default_params };
          });
        }
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [currentProject]);

  useEffect(() => {
    if (!linkedChunkCaches.some((cache) => cache.id === selectedCacheId)) {
      setSelectedCacheId(linkedChunkCaches[0]?.id ?? "");
    }
  }, [linkedChunkCaches, selectedCacheId]);

  async function refreshChunkCaches(projectId: string) {
    const cacheResult = await listDerivedCaches(projectId, "chunks");
    setChunkCaches(cacheResult.derived_caches);
    return cacheResult.derived_caches;
  }

  function updateAsset(assetId: string) {
    setSelectedAssetId(assetId);
    setSelectedCacheId("");
    setPreview(null);
  }

  function updateStrategy(strategyId: string) {
    const strategy = strategies.find((item) => item.id === strategyId);
    if (!strategy) {
      return;
    }
    setChunking({ strategy: strategy.id, params: strategy.default_params });
    setSelectedParameterSetId("");
    setPreview(null);
  }

  function updateChunkingParam(name: string, value: ChunkingParamValue) {
    setChunking((current) => ({ ...current, params: { ...current.params, [name]: value } }));
    setSelectedParameterSetId("");
    setPreview(null);
  }

  async function handlePreview() {
    if (!currentProject || !selectedAssetId) {
      return;
    }

    setIsPreviewing(true);
    try {
      const result = await previewChunking(currentProject.id, {
        chunking,
        data_asset_id: selectedAssetId,
        max_chunks: maxChunks,
      });
      setPreview(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to preview chunks");
    } finally {
      setIsPreviewing(false);
    }
  }

  async function handleMaterialize() {
    if (!currentProject || !selectedAssetId || isMaterializing) {
      return;
    }
    setIsMaterializing(true);
    try {
      const cache = await materializeChunks(currentProject.id, {
        chunking,
        data_asset_id: selectedAssetId,
      });
      await refreshChunkCaches(currentProject.id);
      setSelectedCacheId(cache.id);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to materialize chunks");
    } finally {
      setIsMaterializing(false);
    }
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentProject || !name.trim()) {
      return;
    }

    setIsSaving(true);
    try {
      const paramsHash = `sha256:${await sha256Hex(stableStringify(snapshot))}`;
      const parameterSet = await createParameterSet(currentProject.id, {
        category: "chunking",
        description: description.trim() || undefined,
        name: name.trim(),
        params_hash: paramsHash,
        params_json: snapshot,
      });
      setParameterSets((current) => [...current, parameterSet]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save chunking parameters");
    } finally {
      setIsSaving(false);
    }
  }

  function handleApplyPreset(parameterSet: ParameterSet) {
    const maybeChunking = parameterSet.params_json.chunking;
    if (!isChunkingParams(maybeChunking)) {
      setError("Selected ParameterSet does not contain a valid chunking snapshot");
      return;
    }
    const strategy = strategies.find((item) => item.id === maybeChunking.strategy);
    setChunking({
      strategy: maybeChunking.strategy,
      params: strategy ? mergeDefaults(strategy, maybeChunking.params) : maybeChunking.params,
    });
    setName(parameterSet.name);
    setDescription(parameterSet.description ?? "");
    setSelectedParameterSetId(parameterSet.id);
    setPreview(null);
    setError(null);
  }

  async function handleDeleteSelectedPreset() {
    const selectedParameterSet = chunkingParameterSets.find((item) => item.id === selectedParameterSetId);
    if (!currentProject || !selectedParameterSet) {
      return;
    }
    if (!window.confirm(`Delete chunking ParameterSet "${selectedParameterSet.name}"?`)) {
      return;
    }
    try {
      await deleteParameterSet(currentProject.id, selectedParameterSet.id);
      setParameterSets((current) => current.filter((item) => item.id !== selectedParameterSet.id));
      setSelectedParameterSetId("");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete chunking ParameterSet");
    }
  }

  async function handleDeleteCache(cache: DerivedCache) {
    const message = [
      `Delete materialized chunks "${cache.cache_key}"?`,
      "This will also remove dependent runtime caches, such as indexes and retrieval previews created from these chunks.",
      "Prepared data and saved ParameterSets will stay unchanged.",
    ].join("\n\n");
    if (!currentProject || !window.confirm(message)) {
      return;
    }
    try {
      const result = await deleteDerivedCache(currentProject.id, cache.id, {
        cascadeDependents: true,
      });
      setChunkCaches((current) =>
        current.filter((item) => !result.deleted_derived_cache_ids.includes(item.id)),
      );
      if (result.deleted_derived_cache_ids.includes(selectedCacheId)) {
        setSelectedCacheId("");
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete materialized chunks");
    }
  }

  async function handleDownloadAuthoringPack(cache: DerivedCache) {
    if (!currentProject || isDownloadingPack) {
      return;
    }
    setIsDownloadingPack(true);
    try {
      const blob = await downloadGroundTruthAuthoringPack(currentProject.id, cache.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `raglab_gt_authoring_pack_${cache.cache_key}.zip`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download authoring pack");
    } finally {
      setIsDownloadingPack(false);
    }
  }

  function handleUseInRetrieval(cache: DerivedCache) {
    if (!currentProject) {
      return;
    }
    navigate(`/projects/${currentProject.id}/retrieval?chunks_cache_id=${cache.id}`);
  }

  if (!currentProject) {
    return (
      <section className="page">
        <header className="page-header">
          <p className="eyebrow">Pipeline</p>
          <h1>Chunking</h1>
          <p>Select or create a project first.</p>
        </header>
        <div className="empty-state">No project selected.</div>
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Pipeline</p>
        <h1>Chunking</h1>
        <p>Choose a prepared data asset, tune a registered chunking strategy, preview chunks, and materialize a reusable chunks cache.</p>
      </header>

      {error ? <div className="notice">Chunking unavailable: {error}</div> : null}

      {preparedAssets.length === 0 ? (
        <div className="empty-state">Create a prepared data asset on Preparation before previewing chunks.</div>
      ) : (
        <div className="stage-workbench">
          <div className="stage-left">
            <div className="parameter-section">
              <h2>Source And Strategy</h2>
              <label>
                Prepared data asset
                <select value={selectedAssetId} onChange={(event) => updateAsset(event.target.value)}>
                  {preparedAssets.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.name}
                    </option>
                  ))}
                </select>
              </label>
              {selectedAsset ? <PreparedAssetSummary asset={selectedAsset} /> : null}
              <label>
                Strategy
                <select value={chunking.strategy} onChange={(event) => updateStrategy(event.target.value)}>
                  {strategies.map((strategy) => (
                    <option key={strategy.id} value={strategy.id}>
                      {strategy.label}
                    </option>
                  ))}
                </select>
              </label>
              {selectedStrategy ? <p className="form-note">{selectedStrategy.description}</p> : null}
              {strategyWarning ? <div className="notice warning">{strategyWarning}</div> : null}
              <div className="parameter-grid">
                {selectedStrategy?.fields.map((field) => (
                  <ChunkingFieldControl
                    field={field}
                    key={field.name}
                    onChange={(value) => updateChunkingParam(field.name, value)}
                    value={chunking.params[field.name] ?? field.default}
                  />
                ))}
              </div>
            </div>

            <div className="parameter-section">
              <h2>Preview And Materialize</h2>
              <div className="parameter-grid">
                <label>
                  Preview chunks
                  <input
                    max={200}
                    min={1}
                    type="number"
                    value={maxChunks}
                    onChange={(event) => setMaxChunks(Number(event.target.value))}
                  />
                </label>
              </div>
              <div className="row-actions">
                <button className="secondary-action" disabled={isPreviewing || !selectedAssetId} type="button" onClick={handlePreview}>
                  {isPreviewing ? "Previewing..." : "Preview"}
                </button>
                <button className="primary-action" disabled={isMaterializing || !selectedAssetId} type="button" onClick={handleMaterialize}>
                  {isMaterializing ? "Materializing..." : "Materialize Chunks"}
                </button>
              </div>
            </div>

            <form className="parameter-section" onSubmit={handleSave}>
              <h2>Save Parameters</h2>
              <label>
                Name
                <input value={name} onChange={(event) => setName(event.target.value)} required />
              </label>
              <label>
                Description
                <input value={description} onChange={(event) => setDescription(event.target.value)} />
              </label>
              <button className="secondary-action" disabled={isSaving} type="submit">
                {isSaving ? "Saving..." : "Save Chunking ParameterSet"}
              </button>
            </form>

            <div className="parameter-section">
              <h2>Saved Chunking parameters</h2>
              {chunkingParameterSets.length === 0 ? (
                <div className="nested-empty">No chunking parameters saved yet.</div>
              ) : (
                <div className="index-cache-list">
                  {chunkingParameterSets.map((parameterSet) => (
                    <button
                      className={parameterSet.id === selectedParameterSetId ? "cache-item selected" : "cache-item"}
                      key={parameterSet.id}
                      onClick={() => handleApplyPreset(parameterSet)}
                      type="button"
                    >
                      <strong>{parameterSet.name}</strong>
                      <span>{chunkingStrategyLabel(parameterSet)}</span>
                      <small>{parameterSet.params_hash.slice(0, 18)}</small>
                    </button>
                  ))}
                </div>
              )}
              {selectedParameterSetId ? (
                <div className="row-actions">
                <button className="text-action danger" onClick={handleDeleteSelectedPreset} type="button">
                  Delete selected parameters
                </button>
                </div>
              ) : null}
            </div>

            <div className="parameter-section">
              <h2>Materialized Chunks</h2>
              {linkedChunkCaches.length === 0 ? (
                <div className="nested-empty">No materialized chunks for this prepared asset yet.</div>
              ) : (
                <div className="index-cache-list">
                  {linkedChunkCaches.map((cache) => (
                    <button
                      className={cache.id === selectedCache?.id ? "cache-item selected" : "cache-item"}
                      key={cache.id}
                      onClick={() => setSelectedCacheId(cache.id)}
                      type="button"
                    >
                      <strong>{cache.cache_key}</strong>
                      <span>{cacheChunkingStrategy(cache)}</span>
                      <span>{cacheChunkCount(cache)} chunks</span>
                      <small>{cache.params_hash.slice(0, 18)}</small>
                    </button>
                  ))}
                </div>
              )}
              {selectedCache ? (
                <div className="row-actions">
                  <button className="text-action danger" onClick={() => handleDeleteCache(selectedCache)} type="button">
                    Delete selected chunks
                  </button>
                </div>
              ) : null}
            </div>

            <div className="parameter-section">
              <h2>Selected Chunks Actions</h2>
              {selectedCache ? (
                <div className="row-actions">
                  <button className="secondary-action" onClick={() => handleUseInRetrieval(selectedCache)} type="button">
                    Use in Retrieval
                  </button>
                  <button
                    className="secondary-action"
                    disabled={isDownloadingPack}
                    onClick={() => handleDownloadAuthoringPack(selectedCache)}
                    type="button"
                  >
                    {isDownloadingPack ? "Preparing pack..." : "GT authoring pack"}
                  </button>
                </div>
              ) : (
                <div className="nested-empty">Select materialized chunks first.</div>
              )}
            </div>
          </div>

          <div className="stage-right">
            <div className="parameter-section">
              <h2>Chunking Snapshot</h2>
              <pre className="json-preview">{JSON.stringify(snapshot, null, 2)}</pre>
            </div>

            <div className="parameter-section">
              <h2>Prepared Asset Snapshot</h2>
              {selectedAsset ? (
                <pre className="json-preview">
                  {JSON.stringify(
                    {
                      asset_id: selectedAsset.id,
                      data_format: selectedAsset.data_format,
                      files: selectedAsset.current_manifest_json?.files.map((file) => ({
                        name: file.original_name,
                        role: file.role ?? null,
                        size_bytes: file.size_bytes,
                      })) ?? [],
                      manifest_hash: selectedAsset.manifest_hash,
                      preparation: selectedAsset.preparation_params_json ?? {},
                    },
                    null,
                    2,
                  )}
                </pre>
              ) : (
                <div className="nested-empty">No prepared asset selected.</div>
              )}
            </div>

            <div className="parameter-section">
              <h2>Preview</h2>
              {preview ? <ChunkPreviewResult preview={preview} /> : <div className="nested-empty">No preview yet.</div>}
            </div>

            <div className="parameter-section">
              <h2>Selected Chunks Cache</h2>
              {selectedCache ? (
                <pre className="json-preview">{JSON.stringify(selectedCache.metadata_json, null, 2)}</pre>
              ) : (
                <div className="nested-empty">Materialize chunks or select an existing chunks cache.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function PreparedAssetSummary({ asset }: { asset: DataAsset }) {
  const files = asset.current_manifest_json?.files ?? [];
  const pageUnits = files.filter((file) => file.role === "prepared_parent_pages").length;
  const chapterUnits = files.filter((file) => file.role === "prepared_parent_chapters").length;
  return (
    <div className="asset-mini-summary">
      <span>{asset.data_format}</span>
      <span title={asset.manifest_hash ?? undefined}>{shortHash(asset.manifest_hash)}</span>
      <span>{files.length} file(s)</span>
      {pageUnits > 0 ? <span>{pageUnits} page unit file(s)</span> : null}
      {chapterUnits > 0 ? <span>{chapterUnits} chapter unit file(s)</span> : null}
    </div>
  );
}

function ChunkPreviewResult({ preview }: { preview: ChunkingPreviewResponse }) {
  return (
    <div className="chunk-preview">
      <div className="metric-strip">
        <Metric label="Chunks" value={preview.summary.chunk_count} />
        <Metric label="Files" value={preview.summary.files_count} />
        <Metric label="Avg tokens" value={preview.summary.avg_tokens} />
        <Metric label="Max tokens" value={preview.summary.max_tokens} />
      </div>

      {preview.warnings.length > 0 ? (
        <div className="warning-list">
          {preview.warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}

      <div className="file-chunk-list">
        {preview.summary.chunks_by_file.map((item) => (
          <span key={item.source_name}>
            {item.source_name}: {item.chunk_count}
          </span>
        ))}
      </div>

      <div className="chunk-list">
        {preview.chunks.map((chunk) => (
          <article className="chunk-card" key={chunk.chunk_id}>
            <div className="chunk-meta">
              <strong>{chunk.chunk_id}</strong>
              <span>{chunk.source_name}</span>
              {chunk.parent_type ? <span>{chunk.parent_type}</span> : null}
              {chunk.parent_id ? <span>{compactId(chunk.parent_id)}</span> : null}
              {chunk.page_start ? <span>Page {chunk.page_start}{chunk.page_end && chunk.page_end !== chunk.page_start ? `-${chunk.page_end}` : ""}</span> : null}
              <span>{chunk.token_count} tokens</span>
              <span>{chunk.char_count} chars</span>
            </div>
            {chunk.heading_path.length > 0 ? (
              <div className="chunk-heading-path">{chunk.heading_path.join(" / ")}</div>
            ) : null}
            <pre>{chunk.text_preview}</pre>
          </article>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ChunkingFieldControl({
  field,
  onChange,
  value,
}: {
  field: ChunkingStrategy["fields"][number];
  onChange: (value: ChunkingParamValue) => void;
  value: ChunkingParamValue;
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

function mergeDefaults(
  strategy: ChunkingStrategy,
  params: Record<string, ChunkingParamValue>,
): Record<string, ChunkingParamValue> {
  const fieldNames = new Set(strategy.fields.map((field) => field.name));
  return Object.fromEntries(
    Object.entries({ ...strategy.default_params, ...params }).filter(([key]) => fieldNames.has(key)),
  );
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

function parentUnitWarning(asset: DataAsset, strategyId: string): string | null {
  const files = asset.current_manifest_json?.files ?? [];
  if (strategyId === "page_recursive" && !files.some((file) => file.role === "prepared_parent_pages")) {
    return "Selected strategy expects page unit sidecars, but this prepared asset does not include prepared_parent_pages.";
  }
  if (strategyId === "chapter_recursive" && !files.some((file) => file.role === "prepared_parent_chapters")) {
    return "Selected strategy expects chapter unit sidecars, but this prepared asset does not include prepared_parent_chapters.";
  }
  return null;
}

function isChunkingParams(value: unknown): value is ChunkingParams {
  return (
    Boolean(value) &&
    typeof value === "object" &&
    typeof (value as ChunkingParams).strategy === "string" &&
    Boolean((value as ChunkingParams).params) &&
    typeof (value as ChunkingParams).params === "object"
  );
}

function chunkingStrategyLabel(parameterSet: ParameterSet): string {
  const maybeChunking = parameterSet.params_json.chunking;
  return isChunkingParams(maybeChunking) ? maybeChunking.strategy : "chunking";
}

function cacheChunkingStrategy(cache: DerivedCache): string {
  const chunking = cache.metadata_json.chunking;
  if (chunking && typeof chunking === "object" && typeof (chunking as { strategy?: unknown }).strategy === "string") {
    return (chunking as { strategy: string }).strategy;
  }
  return "-";
}

function cacheChunkCount(cache: DerivedCache): number {
  const summary = cache.metadata_json.summary;
  if (summary && typeof summary === "object" && typeof (summary as { chunk_count?: unknown }).chunk_count === "number") {
    return (summary as { chunk_count: number }).chunk_count;
  }
  return typeof cache.metadata_json.chunk_count === "number" ? cache.metadata_json.chunk_count : 0;
}

function shortHash(hash?: string | null): string {
  if (!hash) {
    return "no manifest";
  }
  return hash.replace("sha256:", "").slice(0, 12);
}

function compactId(value: string): string {
  return value.length > 18 ? `${value.slice(0, 18)}...` : value;
}
