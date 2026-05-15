import { FormEvent, useEffect, useState } from "react";

import {
  DataAsset,
  deleteGroundTruthSet,
  GroundTruthSet,
  listDataAssets,
  listGroundTruthSets,
  Project,
  uploadGroundTruthSet,
} from "../api/client";

type GroundTruthPageProps = {
  currentProject: Project | null;
};

export function GroundTruthPage({ currentProject }: GroundTruthPageProps) {
  const [groundTruthSets, setGroundTruthSets] = useState<GroundTruthSet[]>([]);
  const [dataAssets, setDataAssets] = useState<DataAsset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [dataAssetId, setDataAssetId] = useState("");
  const [file, setFile] = useState<File | null>(null);

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
    const form = event.currentTarget;
    if (!currentProject || !name.trim() || !file) {
      return;
    }

    setIsUploading(true);
    try {
      const groundTruthSet = await uploadGroundTruthSet(currentProject.id, {
        data_asset_id: dataAssetId || undefined,
        file,
        name: name.trim(),
      });
      setGroundTruthSets((current) => [...current, groundTruthSet]);
      setName("");
      setDataAssetId("");
      setFile(null);
      form.reset();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload ground truth set");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDelete(groundTruthSet: GroundTruthSet) {
    if (!currentProject || !window.confirm(`Delete ground truth set "${groundTruthSet.name}"?`)) {
      return;
    }
    setDeletingId(groundTruthSet.id);
    try {
      await deleteGroundTruthSet(currentProject.id, groundTruthSet.id);
      setGroundTruthSets((current) => current.filter((item) => item.id !== groundTruthSet.id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete ground truth set");
    } finally {
      setDeletingId(null);
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
        <p>Upload and validate optional chunk-level qrels for retrieval and reranking evaluation.</p>
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
            {dataAssets.filter((asset) => asset.asset_type === "prepared").map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          GT file
          <input
            accept=".json,.jsonl,application/json,application/x-ndjson"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            required
            type="file"
          />
        </label>
        <button disabled={isUploading || !file} type="submit">
          {isUploading ? "Uploading..." : "Upload GT"}
        </button>
      </form>

      {error ? <div className="notice">Ground truth unavailable: {error}</div> : null}

      {groundTruthSets.length === 0 ? (
        <div className="empty-state">No ground truth sets registered for this project yet.</div>
      ) : (
        <div className="table">
          <div className="table-row ground-truth-table table-head">
            <span>ID</span>
            <span>Name</span>
            <span>Status</span>
            <span>Questions</span>
            <span>Chunks file hash</span>
            <span>Actions</span>
          </div>
          {groundTruthSets.map((groundTruthSet) => (
            <div className="table-row ground-truth-table" key={groundTruthSet.id}>
              <span>{groundTruthSet.id}</span>
              <span>{groundTruthSet.name}</span>
              <span>
                <ValidationBadge groundTruthSet={groundTruthSet} />
              </span>
              <span>{formatQuestionSummary(groundTruthSet)}</span>
              <span>{formatShortHash(groundTruthSet.metadata_json.chunks_file_sha256)}</span>
              <span>
                <button
                  className="text-action danger"
                  disabled={deletingId === groundTruthSet.id}
                  onClick={() => handleDelete(groundTruthSet)}
                  type="button"
                >
                  {deletingId === groundTruthSet.id ? "Deleting..." : "Delete"}
                </button>
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ValidationBadge({ groundTruthSet }: { groundTruthSet: GroundTruthSet }) {
  const validation = groundTruthSet.metadata_json.validation as { status?: string; warnings?: string[] } | undefined;
  const status = validation?.status ?? "unvalidated";
  const className = status === "valid" ? "badge good" : status === "invalid" ? "badge danger" : "badge warning";
  const title = validation?.warnings?.join("\n") || undefined;
  return (
    <span className={className} title={title}>
      {status}
    </span>
  );
}

function formatQuestionSummary(groundTruthSet: GroundTruthSet): string {
  const metadata = groundTruthSet.metadata_json;
  const questionCount = formatMetadataValue(metadata.question_count);
  const foundCount = formatMetadataValue(metadata.found_count);
  const notFoundCount = formatMetadataValue(metadata.not_found_count);
  return `${questionCount} total / ${foundCount} found / ${notFoundCount} not found`;
}

function formatMetadataValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function formatShortHash(value: unknown): string {
  const text = formatMetadataValue(value);
  if (text === "-" || text.length <= 18) {
    return text;
  }
  return `${text.slice(0, 18)}...`;
}
