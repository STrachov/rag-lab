import { FormEvent, useEffect, useState } from "react";

import { createParameterSet, listParameterSets, ParameterSet, Project } from "../api/client";

type ParametersPageProps = {
  currentProject: Project | null;
};

const DEFAULT_PARAMS = `{
  "chunking": {
    "strategy": "heading_recursive",
    "chunk_size": 900,
    "chunk_overlap": 120
  },
  "retrieval": {
    "mode": "dense",
    "top_k": 8
  }
}`;

export function ParametersPage({ currentProject }: ParametersPageProps) {
  const [parameterSets, setParameterSets] = useState<ParameterSet[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [paramsJson, setParamsJson] = useState(DEFAULT_PARAMS);

  useEffect(() => {
    if (!currentProject) {
      setParameterSets([]);
      return;
    }

    refreshParameterSets(currentProject.id);
  }, [currentProject]);

  function refreshParameterSets(projectId: string) {
    listParameterSets(projectId)
      .then((result) => {
        setParameterSets(result.parameter_sets);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentProject || !name.trim()) {
      return;
    }

    try {
      const parsedParams = JSON.parse(paramsJson) as Record<string, unknown>;
      const paramsHash = await sha256Hex(JSON.stringify(parsedParams));
      const parameterSet = await createParameterSet(currentProject.id, {
        description: description.trim() || undefined,
        name: name.trim(),
        params_hash: paramsHash,
        params_json: parsedParams,
      });
      setParameterSets((current) => [...current, parameterSet]);
      setName("");
      setDescription("");
      setParamsJson(DEFAULT_PARAMS);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create parameter set");
    }
  }

  if (!currentProject) {
    return (
      <section className="page">
        <header className="page-header">
          <p className="eyebrow">Parameters</p>
          <h1>Parameter Sets</h1>
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
        <h1>Parameter Sets</h1>
        <p>Reusable preparation, chunking, indexing, retrieval, reranking, generation, and evaluation bundles.</p>
      </header>

      <form className="form-panel parameter-form" onSubmit={handleSubmit}>
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Description
          <input value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <label className="json-field">
          Parameters JSON
          <textarea value={paramsJson} onChange={(event) => setParamsJson(event.target.value)} rows={9} />
        </label>
        <button type="submit">Save Parameters</button>
      </form>

      {error ? <div className="notice">Parameter set unavailable: {error}</div> : null}

      {parameterSets.length === 0 ? (
        <div className="empty-state">No parameter sets saved for this project yet.</div>
      ) : (
        <div className="table">
          <div className="table-row parameter-table table-head">
            <span>ID</span>
            <span>Name</span>
            <span>Description</span>
            <span>Hash</span>
            <span>Created</span>
          </div>
          {parameterSets.map((parameterSet) => (
            <div className="table-row parameter-table" key={parameterSet.id}>
              <span>{parameterSet.id}</span>
              <span>{parameterSet.name}</span>
              <span>{parameterSet.description ?? "-"}</span>
              <span>{parameterSet.params_hash.slice(0, 16)}</span>
              <span>{new Date(parameterSet.created_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

async function sha256Hex(input: string): Promise<string> {
  const encoded = new TextEncoder().encode(input);
  const digest = await window.crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}
