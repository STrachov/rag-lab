import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  DataAsset,
  ParameterSet,
  PreparationMethod,
  Project,
  createParameterSet,
  deleteDataAsset,
  deleteParameterSet,
  getDataAssetFileDownloadUrl,
  listDataAssets,
  listParameterSets,
  listPreparationMethods,
  prepareDataAsset,
} from "../api/client";

type PreparationPageProps = {
  currentProject: Project | null;
};

export function PreparationPage({ currentProject }: PreparationPageProps) {
  const [dataAssets, setDataAssets] = useState<DataAsset[]>([]);
  const [methods, setMethods] = useState<PreparationMethod[]>([]);
  const [parameterSets, setParameterSets] = useState<ParameterSet[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [selectedMethodId, setSelectedMethodId] = useState("");
  const [selectedPreparedId, setSelectedPreparedId] = useState("");
  const [preparedName, setPreparedName] = useState("");
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [presetName, setPresetName] = useState("");
  const [presetDescription, setPresetDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isSavingPreset, setIsSavingPreset] = useState(false);

  const sourceAssets = useMemo(
    () => dataAssets.filter((asset) => asset.asset_type === "raw"),
    [dataAssets],
  );
  const preparedAssets = useMemo(
    () => dataAssets.filter((asset) => asset.asset_type === "prepared"),
    [dataAssets],
  );
  const preparationParameterSets = useMemo(
    () => parameterSets.filter((set) => set.category === "preparation"),
    [parameterSets],
  );
  const selectedSource = sourceAssets.find((asset) => asset.id === selectedSourceId) ?? null;
  const selectedMethod = methods.find((method) => method.id === selectedMethodId) ?? null;
  const linkedPreparedAssets = selectedSource
    ? preparedAssets.filter((asset) => asset.parent_id === selectedSource.id)
    : [];
  const selectedPreparedAsset =
    linkedPreparedAssets.find((asset) => asset.id === selectedPreparedId) ?? linkedPreparedAssets[0] ?? null;
  const snapshot = selectedMethod
    ? {
        preparation: {
          method_id: selectedMethod.id,
          output_formats: selectedMethod.output_formats,
          params,
        },
      }
    : {};

  useEffect(() => {
    if (!currentProject) {
      setDataAssets([]);
      setMethods([]);
      setParameterSets([]);
      return;
    }

    refreshDataAssets(currentProject.id);
    refreshParameterSets(currentProject.id);
    listPreparationMethods(currentProject.id)
      .then((result) => {
        setMethods(result.methods);
        setError(null);
      })
      .catch((err: Error) => {
        setMethods([]);
        setError(`Preparation catalog unavailable: ${err.message}`);
      });
  }, [currentProject]);

  useEffect(() => {
    if (!selectedSourceId && sourceAssets[0]) {
      setSelectedSourceId(sourceAssets[0].id);
    }
  }, [selectedSourceId, sourceAssets]);

  useEffect(() => {
    if (!linkedPreparedAssets.some((asset) => asset.id === selectedPreparedId)) {
      setSelectedPreparedId(linkedPreparedAssets[0]?.id ?? "");
    }
  }, [linkedPreparedAssets, selectedPreparedId]);

  useEffect(() => {
    if (!selectedMethodId && methods[0]) {
      setSelectedMethodId(methods[0].id);
      setParams(defaultParams(methods[0]));
    }
  }, [methods, selectedMethodId]);

  useEffect(() => {
    if (!selectedSource || !selectedMethod) {
      setPreparedName("");
      return;
    }
    setPreparedName(`${selectedSource.name} ${selectedMethod.id}`);
    setPresetName((current) => current || `${selectedMethod.label} default`);
  }, [selectedMethod, selectedSource]);

  async function refreshDataAssets(projectId: string) {
    return listDataAssets(projectId)
      .then((result) => {
        setDataAssets(result.data_assets);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }

  async function refreshParameterSets(projectId: string) {
    return listParameterSets(projectId)
      .then((result) => {
        setParameterSets(result.parameter_sets);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }

  function updateParam(fieldName: string, value: unknown) {
    setParams((current) => ({ ...current, [fieldName]: value }));
  }

  function handleMethodChange(methodId: string) {
    setSelectedMethodId(methodId);
    const method = methods.find((item) => item.id === methodId);
    setParams(method ? defaultParams(method) : {});
  }

  async function handleRunPreparation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentProject || !selectedSource || !selectedMethod || isRunning) {
      return;
    }
    setIsRunning(true);
    try {
      const prepared = await prepareDataAsset(currentProject.id, selectedSource.id, {
        method_id: selectedMethod.id,
        name: preparedName.trim() || undefined,
        params,
      });
      await refreshDataAssets(currentProject.id);
      setSelectedPreparedId(prepared.id);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to prepare source data");
    } finally {
      setIsRunning(false);
    }
  }

  async function handleSavePreset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentProject || !selectedMethod || !presetName.trim() || isSavingPreset) {
      return;
    }
    setIsSavingPreset(true);
    try {
      const paramsJson = snapshot;
      const paramsHash = `sha256:${await sha256Hex(stableStringify(paramsJson))}`;
      const parameterSet = await createParameterSet(currentProject.id, {
        category: "preparation",
        description: presetDescription.trim() || undefined,
        name: presetName.trim(),
        params_hash: paramsHash,
        params_json: paramsJson,
      });
      setParameterSets((current) => [...current, parameterSet]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preparation parameters");
    } finally {
      setIsSavingPreset(false);
    }
  }

  function handleApplyPreset(parameterSet: ParameterSet) {
    const preparation = parameterSet.params_json.preparation;
    if (!isPreparationSnapshot(preparation)) {
      setError("Selected ParameterSet does not contain a valid preparation snapshot");
      return;
    }
    setSelectedMethodId(preparation.method_id);
    setParams(preparation.params);
    setPresetName(parameterSet.name);
    setPresetDescription(parameterSet.description ?? "");
    setError(null);
  }

  async function handleDeletePreset(parameterSet: ParameterSet) {
    if (!currentProject || !window.confirm(`Delete preparation ParameterSet "${parameterSet.name}"?`)) {
      return;
    }
    try {
      await deleteParameterSet(currentProject.id, parameterSet.id);
      setParameterSets((current) => current.filter((item) => item.id !== parameterSet.id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete preparation ParameterSet");
    }
  }

  async function handleDeletePreparedAsset(asset: DataAsset) {
    if (!currentProject || !window.confirm(`Delete prepared asset "${asset.name}"?`)) {
      return;
    }
    try {
      const result = await deleteDataAsset(currentProject.id, asset.id);
      setDataAssets((current) =>
        current.filter((item) => !result.deleted_data_asset_ids.includes(item.id)),
      );
      if (selectedPreparedId === asset.id) {
        setSelectedPreparedId("");
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete prepared asset");
    }
  }

  if (!currentProject) {
    return (
      <section className="page">
        <header className="page-header">
          <p className="eyebrow">Pipeline</p>
          <h1>Preparation</h1>
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
        <h1>Preparation</h1>
        <p>Choose a source data asset, select a registered preparation method, tune params, and materialize a prepared data asset.</p>
      </header>

      {error ? <div className="notice">Preparation unavailable: {error}</div> : null}

      {sourceAssets.length === 0 ? (
        <div className="empty-state">Upload source data on the Data page before preparing it.</div>
      ) : (
        <div className="stage-workbench">
          <div className="stage-left">
            <form className="parameter-section" onSubmit={handleRunPreparation}>
              <h2>Run Preparation</h2>
              <label>
                Source data
                <select value={selectedSourceId} onChange={(event) => setSelectedSourceId(event.target.value)}>
                  {sourceAssets.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Prepared version name
                <input value={preparedName} onChange={(event) => setPreparedName(event.target.value)} required />
              </label>
              <label>
                Method
                <select
                  disabled={methods.length === 0}
                  value={selectedMethodId}
                  onChange={(event) => handleMethodChange(event.target.value)}
                >
                  {methods.map((method) => (
                    <option key={method.id} value={method.id}>
                      {method.label}
                    </option>
                  ))}
                </select>
              </label>
              {selectedMethod ? (
                <div className="asset-mini-summary">
                  <span>{selectedMethod.id}</span>
                  <span>{selectedMethod.output_formats.join(", ")}</span>
                  <span>{shortHash(selectedSource?.manifest_hash)}</span>
                </div>
              ) : null}
              <div className="parameter-grid">
                {selectedMethod?.fields.map((field) => (
                  <PreparationField
                    field={field}
                    key={field.name}
                    onChange={(value) => updateParam(field.name, value)}
                    value={params[field.name] ?? field.default}
                  />
                ))}
              </div>
              {isRunning ? <div className="notice neutral">Preparation is running. This can take a while on CPU.</div> : null}
              <button className="primary-action" disabled={!selectedMethod || isRunning} type="submit">
                {isRunning ? "Running..." : "Run Preparation"}
              </button>
            </form>

            <form className="parameter-section" onSubmit={handleSavePreset}>
              <h2>Save ParameterSet</h2>
              <label>
                Name
                <input value={presetName} onChange={(event) => setPresetName(event.target.value)} required />
              </label>
              <label>
                Description
                <input value={presetDescription} onChange={(event) => setPresetDescription(event.target.value)} />
              </label>
              <button className="secondary-action" disabled={!selectedMethod || isSavingPreset} type="submit">
                {isSavingPreset ? "Saving..." : "Save Preparation ParameterSet"}
              </button>
            </form>

            <div className="parameter-section">
              <h2>Saved Preparation ParameterSets</h2>
              {preparationParameterSets.length === 0 ? (
                <div className="nested-empty">No preparation ParameterSets saved yet.</div>
              ) : (
                <div className="index-cache-list">
                  {preparationParameterSets.map((parameterSet) => (
                    <div className="cache-item" key={parameterSet.id}>
                      <strong>{parameterSet.name}</strong>
                      <span>{preparationMethodLabel(parameterSet)}</span>
                      <small>{parameterSet.params_hash.slice(0, 18)}</small>
                      <div className="row-actions">
                        <button className="text-action" onClick={() => handleApplyPreset(parameterSet)} type="button">
                          Apply
                        </button>
                        <button className="text-action danger" onClick={() => handleDeletePreset(parameterSet)} type="button">
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="parameter-section">
              <h2>Prepared Outputs</h2>
              {linkedPreparedAssets.length === 0 ? (
                <div className="nested-empty">No prepared assets from this source yet.</div>
              ) : (
                <div className="index-cache-list">
                  {linkedPreparedAssets.map((asset) => {
                    const provenance = asset.preparation_params_json ?? {};
                    return (
                      <button
                        className={asset.id === selectedPreparedAsset?.id ? "cache-item selected" : "cache-item"}
                        key={asset.id}
                        onClick={() => setSelectedPreparedId(asset.id)}
                        type="button"
                      >
                        <strong>{asset.name}</strong>
                        <span>{asset.data_format}</span>
                        <span>{String(provenance.method_id ?? provenance.method ?? "-")}</span>
                        <small>{shortHash(asset.manifest_hash)}</small>
                      </button>
                    );
                  })}
                </div>
              )}
              {selectedPreparedAsset ? (
                <button
                  className="text-action danger"
                  onClick={() => handleDeletePreparedAsset(selectedPreparedAsset)}
                  type="button"
                >
                  Delete selected prepared asset
                </button>
              ) : null}
            </div>
          </div>

          <div className="stage-right">
            <div className="parameter-section">
              <h2>Preparation Snapshot</h2>
              <pre className="json-preview">{JSON.stringify(snapshot, null, 2)}</pre>
            </div>

            <div className="parameter-section">
              <h2>Source Manifest</h2>
              {selectedSource ? (
                <AssetDetails asset={selectedSource} projectId={currentProject.id} />
              ) : (
                <div className="nested-empty">No source selected.</div>
              )}
            </div>

            <div className="parameter-section">
              <h2>Selected Prepared Asset</h2>
              {selectedPreparedAsset ? (
                <>
                  <AssetDetails asset={selectedPreparedAsset} projectId={currentProject.id} />
                  <h3>Applied Snapshot</h3>
                  <pre className="json-preview">
                    {JSON.stringify(selectedPreparedAsset.preparation_params_json ?? {}, null, 2)}
                  </pre>
                </>
              ) : (
                <div className="nested-empty">Run preparation or select a prepared output.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function AssetDetails({ asset, projectId }: { asset: DataAsset; projectId: string }) {
  const files = asset.current_manifest_json?.files ?? [];
  const parentUnitSummary = summarizeParentUnitFiles(files);
  return (
    <div className="stage-details">
      <div className="asset-mini-summary">
        <span>{asset.name}</span>
        <span>{asset.data_format}</span>
        <span>{asset.asset_type}</span>
        <span>{shortHash(asset.manifest_hash)}</span>
      </div>
      {parentUnitSummary.length > 0 ? (
        <div className="asset-mini-summary">
          {parentUnitSummary.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      ) : null}
      <div className="file-list compact-file-list">
        {files.length === 0 ? <div className="nested-empty">No files in current manifest.</div> : null}
        {files.map((file) => (
          <div className="file-row compact-file-row" key={file.stored_path}>
            <span title={file.original_name}>{compactFilename(file.original_name)}</span>
            <span>
              <a
                className="file-link"
                href={getDataAssetFileDownloadUrl(projectId, asset.id, file.stored_path)}
                title={`Download ${file.original_name}`}
              >
                {preparedFileKind(file)}
              </a>
            </span>
            <span>{formatBytes(file.size_bytes)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function isPreparationSnapshot(value: unknown): value is { method_id: string; params: Record<string, unknown> } {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as { method_id?: unknown; params?: unknown };
  return typeof candidate.method_id === "string" && Boolean(candidate.params) && typeof candidate.params === "object";
}

function preparationMethodLabel(parameterSet: ParameterSet): string {
  const preparation = parameterSet.params_json.preparation;
  if (isPreparationSnapshot(preparation)) {
    return preparation.method_id;
  }
  return "preparation";
}

function compactFilename(name: string, max = 34): string {
  if (name.length <= max) {
    return name;
  }
  const extensionIndex = name.lastIndexOf(".");
  const extension = extensionIndex > 0 ? name.slice(extensionIndex) : "";
  const available = Math.max(12, max - extension.length - 3);
  const left = Math.ceil(available * 0.65);
  const right = available - left;
  return `${name.slice(0, left)}...${right > 0 ? name.slice(-right - extension.length, -extension.length) : ""}${extension}`;
}

function preparedFileKind(file: NonNullable<DataAsset["current_manifest_json"]>["files"][number]): string {
  switch (file.role) {
    case "prepared_markdown":
      return "Markdown";
    case "docling_document_json":
      return "Docling JSON";
    case "prepared_parent_pages":
      return "Page units JSONL";
    case "prepared_parent_chapters":
      return "Chapter units JSONL";
    default:
      return fallbackFileKind(file);
  }
}

function fallbackFileKind(file: NonNullable<DataAsset["current_manifest_json"]>["files"][number]): string {
  const name = file.original_name.toLowerCase();
  if (name.endsWith(".md") || name.endsWith(".markdown")) {
    return "Markdown";
  }
  if (name.endsWith(".json")) {
    return "JSON";
  }
  if (name.endsWith(".jsonl")) {
    return "JSONL";
  }
  if (name.endsWith(".txt")) {
    return "Text";
  }
  return file.content_type ?? "File";
}

function summarizeParentUnitFiles(files: NonNullable<DataAsset["current_manifest_json"]>["files"]): string[] {
  const pages = files.filter((file) => file.role === "prepared_parent_pages").length;
  const chapters = files.filter((file) => file.role === "prepared_parent_chapters").length;
  return [
    pages > 0 ? `${pages} page unit file(s)` : null,
    chapters > 0 ? `${chapters} chapter unit file(s)` : null,
  ].filter((item): item is string => Boolean(item));
}

function PreparationField({
  field,
  onChange,
  value,
}: {
  field: PreparationMethod["fields"][number];
  onChange: (value: unknown) => void;
  value: unknown;
}) {
  if (field.type === "boolean") {
    return (
      <label className="check-row" title={field.help_text ?? undefined}>
        <input checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
        {field.label}
      </label>
    );
  }

  if (field.type === "select") {
    return (
      <label title={field.help_text ?? undefined}>
        {field.label}
        <select value={String(value ?? field.default)} onChange={(event) => onChange(event.target.value)}>
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
          type="number"
          value={Number(value ?? field.default)}
          onChange={(event) => onChange(Number(event.target.value))}
        />
      </label>
    );
  }

  return (
    <label title={field.help_text ?? undefined}>
      {field.label}
      <input value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function defaultParams(method: PreparationMethod): Record<string, unknown> {
  const fieldDefaults = Object.fromEntries(method.fields.map((field) => [field.name, field.default]));
  return { ...fieldDefaults, ...method.default_params };
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

function shortHash(hash?: string | null): string {
  return hash ? hash.replace("sha256:", "").slice(0, 12) : "-";
}

function formatBytes(bytes?: number) {
  if (!bytes || bytes < 1024) {
    return `${bytes ?? 0} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
