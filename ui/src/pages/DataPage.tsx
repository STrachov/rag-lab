import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  DataAsset,
  Project,
  listDataAssets,
  uploadPreparedDataAsset,
  uploadRawDataAsset,
} from "../api/client";

type DataPageProps = {
  currentProject: Project | null;
};

type DataTab = "raw" | "prepared";

const DEFAULT_PREPARATION_PARAMS = `{
  "method": "external_gpu",
  "tool": "marker",
  "tool_version": "",
  "source_format": "pdf",
  "output_format": "markdown",
  "command": "",
  "settings": {},
  "notes": "Prepared outside RAG Lab and uploaded as Markdown."
}`;

export function DataPage({ currentProject }: DataPageProps) {
  const [activeTab, setActiveTab] = useState<DataTab>("raw");
  const [dataAssets, setDataAssets] = useState<DataAsset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [rawName, setRawName] = useState("");
  const [rawFormat, setRawFormat] = useState("pdf");
  const [rawFiles, setRawFiles] = useState<File[]>([]);
  const [preparedName, setPreparedName] = useState("");
  const [preparedFormat, setPreparedFormat] = useState("markdown");
  const [preparedParentId, setPreparedParentId] = useState("");
  const [preparedFiles, setPreparedFiles] = useState<File[]>([]);
  const [preparationParams, setPreparationParams] = useState(DEFAULT_PREPARATION_PARAMS);

  const rawAssets = useMemo(
    () => dataAssets.filter((asset) => asset.asset_type === "raw"),
    [dataAssets],
  );
  const preparedAssets = useMemo(
    () => dataAssets.filter((asset) => asset.asset_type === "prepared"),
    [dataAssets],
  );

  useEffect(() => {
    if (!currentProject) {
      setDataAssets([]);
      return;
    }

    refreshDataAssets(currentProject.id);
  }, [currentProject]);

  function refreshDataAssets(projectId: string) {
    listDataAssets(projectId)
      .then((result) => {
        setDataAssets(result.data_assets);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }

  async function handleRawUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentProject || !rawName.trim() || rawFiles.length === 0) {
      return;
    }

    try {
      const dataAsset = await uploadRawDataAsset(currentProject.id, {
        data_format: rawFormat,
        files: rawFiles,
        name: rawName.trim(),
      });
      setDataAssets((current) => [...current, dataAsset]);
      setRawName("");
      setRawFormat("pdf");
      setRawFiles([]);
      resetFileInput("raw-files");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload raw data");
    }
  }

  async function handlePreparedUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentProject || !preparedName.trim() || preparedFiles.length === 0) {
      return;
    }

    try {
      const parsedPreparationParams = JSON.parse(preparationParams) as Record<string, unknown>;
      const dataAsset = await uploadPreparedDataAsset(currentProject.id, {
        data_format: preparedFormat,
        files: preparedFiles,
        name: preparedName.trim(),
        parent_id: preparedParentId || undefined,
        preparation_params_json: parsedPreparationParams,
      });
      setDataAssets((current) => [...current, dataAsset]);
      setPreparedName("");
      setPreparedFormat("markdown");
      setPreparedParentId("");
      setPreparedFiles([]);
      setPreparationParams(DEFAULT_PREPARATION_PARAMS);
      resetFileInput("prepared-files");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload prepared data");
    }
  }

  if (!currentProject) {
    return (
      <ScopedEmptyPage
        eyebrow="Data"
        title="Data Assets"
        body="Select or create a project first. Data assets are always registered inside the current project."
      />
    );
  }

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Data</p>
        <h1>Data Assets</h1>
        <p>Upload raw sources and prepared Markdown assets for the current project.</p>
      </header>

      <div className="tabs" role="tablist" aria-label="Data asset type">
        <button
          className={activeTab === "raw" ? "tab active" : "tab"}
          onClick={() => setActiveTab("raw")}
          type="button"
        >
          Raw Data
        </button>
        <button
          className={activeTab === "prepared" ? "tab active" : "tab"}
          onClick={() => setActiveTab("prepared")}
          type="button"
        >
          Prepared Data
        </button>
      </div>

      {activeTab === "raw" ? (
        <RawDataSection
          assets={rawAssets}
          fileCount={rawFiles.length}
          format={rawFormat}
          name={rawName}
          onFilesChange={setRawFiles}
          onFormatChange={setRawFormat}
          onNameChange={setRawName}
          onSubmit={handleRawUpload}
        />
      ) : (
        <PreparedDataSection
          assets={preparedAssets}
          fileCount={preparedFiles.length}
          format={preparedFormat}
          name={preparedName}
          onFilesChange={setPreparedFiles}
          onFormatChange={setPreparedFormat}
          onNameChange={setPreparedName}
          onParentChange={setPreparedParentId}
          onPreparationParamsChange={setPreparationParams}
          onSubmit={handlePreparedUpload}
          parentId={preparedParentId}
          preparationParams={preparationParams}
          rawAssets={rawAssets}
        />
      )}

      {error ? <div className="notice">Data asset unavailable: {error}</div> : null}
    </section>
  );
}

function RawDataSection({
  assets,
  fileCount,
  format,
  name,
  onFilesChange,
  onFormatChange,
  onNameChange,
  onSubmit,
}: {
  assets: DataAsset[];
  fileCount: number;
  format: string;
  name: string;
  onFilesChange: (files: File[]) => void;
  onFormatChange: (format: string) => void;
  onNameChange: (name: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <>
      <form className="form-panel upload-form" onSubmit={onSubmit}>
        <label>
          Name
          <input value={name} onChange={(event) => onNameChange(event.target.value)} required />
        </label>
        <label>
          Format
          <select value={format} onChange={(event) => onFormatChange(event.target.value)}>
            <option value="pdf">pdf</option>
            <option value="docx">docx</option>
            <option value="html">html</option>
            <option value="mixed">mixed</option>
            <option value="other">other</option>
          </select>
        </label>
        <label>
          Files
          <input
            id="raw-files"
            multiple
            onChange={(event) => onFilesChange(Array.from(event.target.files ?? []))}
            type="file"
          />
        </label>
        <button disabled={fileCount === 0} type="submit">
          Upload Raw Data
        </button>
        <span className="form-note">{fileCount} file(s) selected</span>
      </form>

      <DataAssetTable assets={assets} emptyMessage="No raw data uploaded for this project yet." />
    </>
  );
}

function PreparedDataSection({
  assets,
  fileCount,
  format,
  name,
  onFilesChange,
  onFormatChange,
  onNameChange,
  onParentChange,
  onPreparationParamsChange,
  onSubmit,
  parentId,
  preparationParams,
  rawAssets,
}: {
  assets: DataAsset[];
  fileCount: number;
  format: string;
  name: string;
  onFilesChange: (files: File[]) => void;
  onFormatChange: (format: string) => void;
  onNameChange: (name: string) => void;
  onParentChange: (parentId: string) => void;
  onPreparationParamsChange: (params: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  parentId: string;
  preparationParams: string;
  rawAssets: DataAsset[];
}) {
  return (
    <>
      <form className="form-panel prepared-upload-form" onSubmit={onSubmit}>
        <label>
          Name
          <input value={name} onChange={(event) => onNameChange(event.target.value)} required />
        </label>
        <label>
          Format
          <select value={format} onChange={(event) => onFormatChange(event.target.value)}>
            <option value="markdown">markdown</option>
            <option value="text">text</option>
            <option value="jsonl">jsonl</option>
            <option value="mixed">mixed</option>
            <option value="other">other</option>
          </select>
        </label>
        <label>
          Parent raw data
          <select value={parentId} onChange={(event) => onParentChange(event.target.value)}>
            <option value="">None</option>
            {rawAssets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Files
          <input
            id="prepared-files"
            multiple
            onChange={(event) => onFilesChange(Array.from(event.target.files ?? []))}
            type="file"
          />
        </label>
        <label className="json-field">
          Preparation metadata JSON
          <textarea
            onChange={(event) => onPreparationParamsChange(event.target.value)}
            rows={10}
            value={preparationParams}
          />
        </label>
        <button disabled={fileCount === 0} type="submit">
          Upload Prepared Data
        </button>
        <span className="form-note">{fileCount} file(s) selected</span>
      </form>

      <DataAssetTable assets={assets} emptyMessage="No prepared data uploaded for this project yet." />
    </>
  );
}

function DataAssetTable({ assets, emptyMessage }: { assets: DataAsset[]; emptyMessage: string }) {
  if (assets.length === 0) {
    return <div className="empty-state">{emptyMessage}</div>;
  }

  return (
    <div className="table">
      <div className="table-row data-table table-head">
        <span>Name</span>
        <span>Format</span>
        <span>Status</span>
        <span>Storage path</span>
        <span>Manifest</span>
      </div>
      {assets.map((asset) => (
        <div className="table-row data-table" key={asset.id}>
          <span>{asset.name}</span>
          <span>{asset.data_format}</span>
          <span>{asset.status}</span>
          <span>{asset.storage_path ?? "-"}</span>
          <span>{asset.manifest_hash ?? "-"}</span>
        </div>
      ))}
    </div>
  );
}

function ScopedEmptyPage({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{body}</p>
      </header>
      <div className="empty-state">No project selected.</div>
    </section>
  );
}

function resetFileInput(id: string) {
  const input = document.getElementById(id);
  if (input instanceof HTMLInputElement) {
    input.value = "";
  }
}
