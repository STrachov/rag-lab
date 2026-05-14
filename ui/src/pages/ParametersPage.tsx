import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  ChunkingParams,
  ChunkingParamValue,
  ChunkingPreviewResponse,
  ChunkingStrategy,
  createParameterSet,
  DataAsset,
  deleteParameterSet,
  listChunkingStrategies,
  listDataAssets,
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

export function ParametersPage({ currentProject }: ParametersPageProps) {
  const [parameterSets, setParameterSets] = useState<ParameterSet[]>([]);
  const [dataAssets, setDataAssets] = useState<DataAsset[]>([]);
  const [strategies, setStrategies] = useState<ChunkingStrategy[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isContinuing, setIsContinuing] = useState(false);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [name, setName] = useState("Dense chunking baseline");
  const [description, setDescription] = useState("");
  const [chunking, setChunking] = useState<ChunkingParams>(DEFAULT_CHUNKING);
  const [preview, setPreview] = useState<ChunkingPreviewResponse | null>(null);

  const preparedAssets = useMemo(
    () => dataAssets.filter((asset) => asset.asset_type === "prepared"),
    [dataAssets],
  );
  const selectedAsset = preparedAssets.find((asset) => asset.id === selectedAssetId);
  const selectedStrategy = strategies.find((strategy) => strategy.id === chunking.strategy);
  const paramsJson = useMemo(() => ({ chunking }), [chunking]);
  const navigate = useNavigate();

  useEffect(() => {
    if (!currentProject) {
      setParameterSets([]);
      setDataAssets([]);
      setStrategies([]);
      setSelectedAssetId("");
      return;
    }

    Promise.all([
      listParameterSets(currentProject.id),
      listDataAssets(currentProject.id),
      listChunkingStrategies(currentProject.id),
    ])
      .then(([parameterResult, assetResult, strategyResult]) => {
        setParameterSets(parameterResult.parameter_sets);
        setDataAssets(assetResult.data_assets);
        setStrategies(strategyResult.strategies);
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

  function updateStrategy(strategyId: string) {
    const strategy = strategies.find((item) => item.id === strategyId);
    if (!strategy) {
      return;
    }
    setChunking({ strategy: strategy.id, params: strategy.default_params });
    setPreview(null);
  }

  function updateChunkingParam(name: string, value: ChunkingParamValue) {
    setChunking((current) => ({ ...current, params: { ...current.params, [name]: value } }));
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
        max_chunks: 50,
        text_preview_chars: 900,
      });
      setPreview(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to preview chunks");
    } finally {
      setIsPreviewing(false);
    }
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentProject || !name.trim()) {
      return;
    }

    setIsSaving(true);
    try {
      const paramsHash = `sha256:${await sha256Hex(stableStringify(paramsJson))}`;
      const parameterSet = await createParameterSet(currentProject.id, {
        category: "chunking",
        description: description.trim() || undefined,
        name: name.trim(),
        params_hash: paramsHash,
        params_json: paramsJson,
      });
      setParameterSets((current) => [...current, parameterSet]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save chunking parameters");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleContinueToIndexing() {
    if (!currentProject || !selectedAssetId) {
      return;
    }
    setIsContinuing(true);
    try {
      const cache = await materializeChunks(currentProject.id, {
        chunking,
        data_asset_id: selectedAssetId,
      });
      setError(null);
      navigate(`/projects/${currentProject.id}/indexing?chunks_cache_id=${cache.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to materialize chunks");
    } finally {
      setIsContinuing(false);
    }
  }

  async function handleDelete(parameterSet: ParameterSet) {
    if (!currentProject) {
      return;
    }
    const confirmed = window.confirm(`Delete parameter set "${parameterSet.name}"?`);
    if (!confirmed) {
      return;
    }

    try {
      await deleteParameterSet(currentProject.id, parameterSet.id);
      setParameterSets((current) => current.filter((item) => item.id !== parameterSet.id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete parameter set");
    }
  }

  if (!currentProject) {
    return (
      <section className="page">
        <header className="page-header">
          <p className="eyebrow">Parameters</p>
          <h1>Chunking Parameters</h1>
          <p>Select or create a project first. Parameter sets are scoped to the current project.</p>
        </header>
        <div className="empty-state">No project selected.</div>
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Parameters</p>
        <h1>Chunking Lab</h1>
        <p>Choose a prepared data asset, tune chunking, inspect the preview, then save a reusable ParameterSet.</p>
      </header>

      {error ? <div className="notice">Chunking unavailable: {error}</div> : null}

      {preparedAssets.length === 0 ? (
        <div className="empty-state">Create a prepared data asset in Data before previewing chunks.</div>
      ) : (
        <div className="parameter-workbench">
          <form className="chunking-form" onSubmit={handleSave}>
            <div className="parameter-section">
              <h2>Source</h2>
              <label>
                Prepared data asset
                <select
                  value={selectedAssetId}
                  onChange={(event) => {
                    setSelectedAssetId(event.target.value);
                    setPreview(null);
                  }}
                >
                  {preparedAssets.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.name}
                    </option>
                  ))}
                </select>
              </label>
              {selectedAsset ? (
                <div className="asset-mini-summary">
                  <span>{selectedAsset.data_format}</span>
                  <span title={selectedAsset.manifest_hash ?? undefined}>
                    {shortHash(selectedAsset.manifest_hash)}
                  </span>
                  <span>{selectedAsset.current_manifest_json?.files.length ?? 0} file(s)</span>
                </div>
              ) : null}
            </div>

            <div className="parameter-section">
              <h2>Chunking</h2>
              <div className="parameter-grid">
                <label>
                  Strategy
                  <select
                    value={chunking.strategy}
                    onChange={(event) => updateStrategy(event.target.value)}
                  >
                    {strategies.map((strategy) => (
                      <option key={strategy.id} value={strategy.id}>
                        {strategy.label}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedStrategy
                  ? selectedStrategy.fields.map((field) => (
                      <ChunkingFieldControl
                        field={field}
                        key={field.name}
                        value={chunking.params[field.name] ?? field.default}
                        onChange={(value) => updateChunkingParam(field.name, value)}
                      />
                    ))
                  : null}
              </div>
              {selectedStrategy ? <p className="form-note">{selectedStrategy.description}</p> : null}
              <button className="secondary-action" disabled={isPreviewing || !selectedAssetId} type="button" onClick={handlePreview}>
                {isPreviewing ? "Previewing..." : "Preview chunks"}
              </button>
              <button
                className="primary-action"
                disabled={isContinuing || !selectedAssetId}
                type="button"
                onClick={handleContinueToIndexing}
              >
                {isContinuing ? "Materializing..." : "Next: Embedding & Qdrant"}
              </button>
            </div>

            <div className="parameter-section">
              <h2>Save ParameterSet</h2>
              <div className="parameter-grid">
                <label>
                  Name
                  <input value={name} onChange={(event) => setName(event.target.value)} required />
                </label>
                <label>
                  Description
                  <input value={description} onChange={(event) => setDescription(event.target.value)} />
                </label>
              </div>
              <button className="primary-action" disabled={isSaving} type="submit">
                {isSaving ? "Saving..." : "Save chunking parameters"}
              </button>
            </div>
          </form>

          <div className="chunk-preview-panel">
            <div className="parameter-section">
              <h2>Preview</h2>
              {preview ? <ChunkPreviewResult preview={preview} /> : <div className="nested-empty">No preview yet.</div>}
            </div>

            <div className="parameter-section">
              <h2>Snapshot</h2>
              <pre className="json-preview">{JSON.stringify(paramsJson, null, 2)}</pre>
            </div>
          </div>
        </div>
      )}

      <SavedParameterSets parameterSets={parameterSets} onDelete={handleDelete} />
    </section>
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
              {chunk.page ? <span>Page {chunk.page}</span> : null}
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

function SavedParameterSets({
  onDelete,
  parameterSets,
}: {
  onDelete: (parameterSet: ParameterSet) => void;
  parameterSets: ParameterSet[];
}) {
  if (parameterSets.length === 0) {
    return <div className="empty-state">No parameter sets saved for this project yet.</div>;
  }

  return (
    <div className="table">
      <div className="table-row parameter-table table-head">
        <span>ID</span>
        <span>Name</span>
        <span>Category</span>
        <span>Description</span>
        <span>Hash</span>
        <span>Created</span>
        <span>Actions</span>
      </div>
      {parameterSets.map((parameterSet) => (
        <div className="table-row parameter-table" key={parameterSet.id}>
          <span>{parameterSet.id}</span>
          <span>{parameterSet.name}</span>
          <span>{parameterSet.category}</span>
          <span>{parameterSet.description ?? "-"}</span>
          <span>{parameterSet.params_hash.slice(0, 18)}</span>
          <span>{new Date(parameterSet.created_at).toLocaleString()}</span>
          <span>
            <button className="text-action danger" onClick={() => onDelete(parameterSet)} type="button">
              Delete
            </button>
          </span>
        </div>
      ))}
    </div>
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

function shortHash(hash?: string | null): string {
  if (!hash) {
    return "no manifest";
  }
  return hash.length > 18 ? `${hash.slice(0, 18)}...` : hash;
}
