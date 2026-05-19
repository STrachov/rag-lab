import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  DataAsset,
  PreparationMethod,
  Project,
  createParameterSet,
  listDataAssets,
  listPreparationMethods,
  prepareDataAsset,
} from "../api/client";

type PreparationPageProps = {
  currentProject: Project | null;
};

export function PreparationPage({ currentProject }: PreparationPageProps) {
  const [dataAssets, setDataAssets] = useState<DataAsset[]>([]);
  const [methods, setMethods] = useState<PreparationMethod[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [selectedMethodId, setSelectedMethodId] = useState("");
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
  const selectedSource = sourceAssets.find((asset) => asset.id === selectedSourceId) ?? null;
  const selectedMethod = methods.find((method) => method.id === selectedMethodId) ?? null;
  const linkedPreparedAssets = selectedSource
    ? preparedAssets.filter((asset) => asset.parent_id === selectedSource.id)
    : [];
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
      return;
    }

    refreshDataAssets(currentProject.id);
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
    if (!selectedMethodId && methods[0]) {
      setSelectedMethodId(methods[0].id);
    }
  }, [methods, selectedMethodId]);

  useEffect(() => {
    if (!selectedMethod) {
      setParams({});
      return;
    }
    setParams(defaultParams(selectedMethod));
  }, [selectedMethod]);

  useEffect(() => {
    if (!selectedSource || !selectedMethod) {
      setPreparedName("");
      return;
    }
    setPreparedName(`${selectedSource.name} ${selectedMethod.id}`);
    setPresetName(`${selectedMethod.label} default`);
  }, [selectedMethod, selectedSource]);

  async function refreshDataAssets(projectId: string) {
    return listDataAssets(projectId)
      .then((result) => {
        setDataAssets(result.data_assets);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }

  function updateParam(fieldName: string, value: unknown) {
    setParams((current) => ({ ...current, [fieldName]: value }));
  }

  async function handleRunPreparation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentProject || !selectedSource || !selectedMethod || isRunning) {
      return;
    }
    setIsRunning(true);
    try {
      await prepareDataAsset(currentProject.id, selectedSource.id, {
        method_id: selectedMethod.id,
        name: preparedName.trim() || undefined,
        params,
      });
      await refreshDataAssets(currentProject.id);
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
      await createParameterSet(currentProject.id, {
        category: "preparation",
        description: presetDescription.trim() || undefined,
        name: presetName.trim(),
        params_hash: paramsHash,
        params_json: paramsJson,
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preparation parameters");
    } finally {
      setIsSavingPreset(false);
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
        <div className="preparation-workbench">
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
                onChange={(event) => setSelectedMethodId(event.target.value)}
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

          <div className="parameter-section">
            <h2>Preparation Snapshot</h2>
            <pre className="json-preview">{JSON.stringify(snapshot, null, 2)}</pre>
            <form className="preset-form" onSubmit={handleSavePreset}>
              <label>
                ParameterSet name
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
          </div>

          <div className="parameter-section preparation-results">
            <h2>Prepared Outputs</h2>
            {selectedSource ? (
              <div className="asset-mini-summary">
                <span>{selectedSource.name}</span>
                <span>{selectedSource.data_format}</span>
                <span>{shortHash(selectedSource.manifest_hash)}</span>
              </div>
            ) : null}
            {linkedPreparedAssets.length === 0 ? (
              <div className="nested-empty">No prepared assets from this source yet.</div>
            ) : (
              <div className="index-cache-list">
                {linkedPreparedAssets.map((asset) => {
                  const provenance = asset.preparation_params_json ?? {};
                  return (
                    <div className="cache-item" key={asset.id}>
                      <strong>{asset.name}</strong>
                      <span>{asset.data_format}</span>
                      <span>{String(provenance.method_id ?? provenance.method ?? "-")}</span>
                      <small>{shortHash(asset.manifest_hash)}</small>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
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
