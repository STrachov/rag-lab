import { FormEvent, useEffect, useState } from "react";

import {
  createGroundTruthSet,
  DataAsset,
  GroundTruthSet,
  listDataAssets,
  listGroundTruthSets,
  Project,
} from "../api/client";

type GroundTruthPageProps = {
  currentProject: Project | null;
};

export function GroundTruthPage({ currentProject }: GroundTruthPageProps) {
  const [groundTruthSets, setGroundTruthSets] = useState<GroundTruthSet[]>([]);
  const [dataAssets, setDataAssets] = useState<DataAsset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [dataAssetId, setDataAssetId] = useState("");
  const [storagePath, setStoragePath] = useState("");
  const [manifestHash, setManifestHash] = useState("");

  useEffect(() => {
    if (!currentProject) {
      setGroundTruthSets([]);
      setDataAssets([]);
      return;
    }

    refresh(currentProject.id);
  }, [currentProject]);

  function refresh(projectId: string) {
    Promise.all([listGroundTruthSets(projectId), listDataAssets(projectId)])
      .then(([groundTruthResult, dataAssetResult]) => {
        setGroundTruthSets(groundTruthResult.ground_truth_sets);
        setDataAssets(dataAssetResult.data_assets);
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
      const groundTruthSet = await createGroundTruthSet(currentProject.id, {
        data_asset_id: dataAssetId || undefined,
        manifest_hash: manifestHash.trim() || undefined,
        name: name.trim(),
        storage_path: storagePath.trim() || undefined,
      });
      setGroundTruthSets((current) => [...current, groundTruthSet]);
      setName("");
      setDataAssetId("");
      setStoragePath("");
      setManifestHash("");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create ground truth set");
    }
  }

  if (!currentProject) {
    return (
      <section className="page">
        <header className="page-header">
          <p className="eyebrow">Ground Truth</p>
          <h1>Ground Truth Sets</h1>
          <p>Select or create a project first. Ground truth sets are scoped to the current project.</p>
        </header>
        <div className="empty-state">No project selected.</div>
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Ground Truth</p>
        <h1>Ground Truth Sets</h1>
        <p>Optional expected facts, sources, labels, and judgment references for the current project.</p>
      </header>

      <form className="form-panel ground-truth-form" onSubmit={handleSubmit}>
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Data asset
          <select value={dataAssetId} onChange={(event) => setDataAssetId(event.target.value)}>
            <option value="">None</option>
            {dataAssets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Storage path
          <input value={storagePath} onChange={(event) => setStoragePath(event.target.value)} />
        </label>
        <label>
          Manifest hash
          <input value={manifestHash} onChange={(event) => setManifestHash(event.target.value)} />
        </label>
        <button type="submit">Add Ground Truth</button>
      </form>

      {error ? <div className="notice">Ground truth unavailable: {error}</div> : null}

      {groundTruthSets.length === 0 ? (
        <div className="empty-state">No ground truth sets registered for this project yet.</div>
      ) : (
        <div className="table">
          <div className="table-row ground-truth-table table-head">
            <span>ID</span>
            <span>Name</span>
            <span>Data asset</span>
            <span>Storage path</span>
            <span>Manifest</span>
          </div>
          {groundTruthSets.map((groundTruthSet) => (
            <div className="table-row ground-truth-table" key={groundTruthSet.id}>
              <span>{groundTruthSet.id}</span>
              <span>{groundTruthSet.name}</span>
              <span>{groundTruthSet.data_asset_id ?? "-"}</span>
              <span>{groundTruthSet.storage_path ?? "-"}</span>
              <span>{groundTruthSet.manifest_hash ?? "-"}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
