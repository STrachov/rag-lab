import { FormEvent, useEffect, useState } from "react";

import {
  DataAsset,
  DerivedCache,
  GroundTruthSet,
  listDataAssets,
  listDerivedCaches,
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
  const [chunksCaches, setChunksCaches] = useState<DerivedCache[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [name, setName] = useState("");
  const [dataAssetId, setDataAssetId] = useState("");
  const [chunksCacheId, setChunksCacheId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const visibleChunksCaches = dataAssetId
    ? chunksCaches.filter((cache) => cache.data_asset_id === dataAssetId)
    : chunksCaches;

  useEffect(() => {
    if (!currentProject) {
      setGroundTruthSets([]);
      setDataAssets([]);
      setChunksCaches([]);
      return;
    }

    refresh(currentProject.id);
  }, [currentProject]);

  function refresh(projectId: string) {
    Promise.all([listGroundTruthSets(projectId), listDataAssets(projectId), listDerivedCaches(projectId, "chunks")])
      .then(([groundTruthResult, dataAssetResult, chunksResult]) => {
        setGroundTruthSets(groundTruthResult.ground_truth_sets);
        setDataAssets(dataAssetResult.data_assets);
        setChunksCaches(chunksResult.derived_caches.filter((cache) => cache.status === "ready"));
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentProject || !name.trim() || !file) {
      return;
    }

    setIsUploading(true);
    try {
      const groundTruthSet = await uploadGroundTruthSet(currentProject.id, {
        chunks_cache_id: chunksCacheId || undefined,
        data_asset_id: dataAssetId || undefined,
        file,
        name: name.trim(),
      });
      setGroundTruthSets((current) => [...current, groundTruthSet]);
      setName("");
      setDataAssetId("");
      setChunksCacheId("");
      setFile(null);
      event.currentTarget.reset();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload ground truth set");
    } finally {
      setIsUploading(false);
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
          <select
            value={dataAssetId}
            onChange={(event) => {
              const nextDataAssetId = event.target.value;
              setDataAssetId(nextDataAssetId);
              const selectedCache = chunksCaches.find((cache) => cache.id === chunksCacheId);
              if (nextDataAssetId && selectedCache?.data_asset_id !== nextDataAssetId) {
                setChunksCacheId("");
              }
            }}
          >
            <option value="">Infer from chunks cache</option>
            {dataAssets.filter((asset) => asset.asset_type === "prepared").map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Chunks cache
          <select
            value={chunksCacheId}
            onChange={(event) => {
              const nextChunksCacheId = event.target.value;
              setChunksCacheId(nextChunksCacheId);
              const selectedCache = chunksCaches.find((cache) => cache.id === nextChunksCacheId);
              if (!dataAssetId && selectedCache?.data_asset_id) {
                setDataAssetId(selectedCache.data_asset_id);
              }
            }}
          >
            <option value="">None</option>
            {visibleChunksCaches.map((cache) => (
              <option key={cache.id} value={cache.id}>
                {cache.cache_key}
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
            <span>Chunks cache</span>
          </div>
          {groundTruthSets.map((groundTruthSet) => (
            <div className="table-row ground-truth-table" key={groundTruthSet.id}>
              <span>{groundTruthSet.id}</span>
              <span>{groundTruthSet.name}</span>
              <span>
                <ValidationBadge groundTruthSet={groundTruthSet} />
              </span>
              <span>{formatQuestionSummary(groundTruthSet)}</span>
              <span>{formatMetadataValue(groundTruthSet.metadata_json.chunks_cache_key)}</span>
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
