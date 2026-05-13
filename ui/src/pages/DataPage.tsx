import { FormEvent, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import {
  DataAsset,
  DataAssetManifestFile,
  PreparationMethod,
  Project,
  addDataAssetFiles,
  deleteDataAsset,
  deleteDataAssetFile,
  getDataAssetFileDownloadUrl,
  listDataAssets,
  listPreparationMethods,
  prepareDataAsset,
  uploadPreparedDataAsset,
  uploadRawDataAsset,
} from "../api/client";

type DataPageProps = {
  currentProject: Project | null;
};

type ModalKind = "source" | "prepared" | null;

const DEFAULT_PREPARATION_METHODS: PreparationMethod[] = [
  {
    description: "CPU text extraction for PDFs with extractable text layers, plus text and Markdown inputs.",
    fields: [{ default: true, label: "Page breaks", name: "page_breaks", type: "boolean" }],
    id: "pymupdf_text",
    label: "PyMuPDF text",
    output_formats: ["markdown"],
  },
  {
    description: "Convert through Docling Serve and store Markdown plus Docling JSON.",
    fields: [
      { default: true, label: "OCR", name: "docling_do_ocr", type: "boolean" },
      { default: false, label: "Force OCR", name: "docling_force_ocr", type: "boolean" },
    ],
    id: "docling",
    label: "Docling",
    output_formats: ["markdown", "json"],
  },
];

export function DataPage({ currentProject }: DataPageProps) {
  const [dataAssets, setDataAssets] = useState<DataAsset[]>([]);
  const [expandedAssetIds, setExpandedAssetIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalKind>(null);
  const [preparationMethods, setPreparationMethods] = useState<PreparationMethod[]>([]);
  const [preparedParent, setPreparedParent] = useState<DataAsset | null>(null);

  const sourceAssets = useMemo(
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
    listPreparationMethods(currentProject.id)
      .then((result) => setPreparationMethods(result.methods))
      .catch(() => setPreparationMethods(DEFAULT_PREPARATION_METHODS));
  }, [currentProject]);

  function refreshDataAssets(projectId: string) {
    listDataAssets(projectId)
      .then((result) => {
        setDataAssets(result.data_assets);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }

  function upsertAsset(asset: DataAsset) {
    setDataAssets((current) => {
      const exists = current.some((item) => item.id === asset.id);
      return exists ? current.map((item) => (item.id === asset.id ? asset : item)) : [...current, asset];
    });
  }

  function removeAsset(assetId: string) {
    setDataAssets((current) => current.filter((asset) => asset.id !== assetId));
  }

  function openPreparedModal(parent: DataAsset) {
    setPreparedParent(parent);
    setModal("prepared");
  }

  function closeModal() {
    setModal(null);
    setPreparedParent(null);
  }

  function toggleAsset(assetId: string) {
    setExpandedAssetIds((current) => {
      const next = new Set(current);
      next.has(assetId) ? next.delete(assetId) : next.add(assetId);
      return next;
    });
  }

  async function handleAddFiles(asset: DataAsset, files: File[]) {
    if (!currentProject || files.length === 0) {
      return;
    }

    try {
      const updated = await addDataAssetFiles(currentProject.id, asset.id, files);
      upsertAsset(updated);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add files");
    }
  }

  async function handleDeleteFile(asset: DataAsset, file: DataAssetManifestFile) {
    if (!currentProject) {
      return;
    }

    try {
      const result = await deleteDataAssetFile(currentProject.id, asset.id, file.stored_path);
      if (result.deleted_data_asset_id) {
        removeAsset(result.deleted_data_asset_id);
      }
      if (result.data_asset) {
        upsertAsset(result.data_asset);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete file");
    }
  }

  async function handleDeleteAsset(asset: DataAsset) {
    if (!currentProject) {
      return;
    }

    const message =
      asset.asset_type === "raw"
        ? `Delete source asset "${asset.name}" and all linked prepared versions?`
        : `Delete prepared version "${asset.name}"?`;
    if (!window.confirm(message)) {
      return;
    }

    try {
      const result = await deleteDataAsset(currentProject.id, asset.id);
      result.deleted_data_asset_ids.forEach(removeAsset);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete data asset");
    }
  }

  async function handlePrepare(asset: DataAsset, method: string, options: Record<string, boolean>) {
    if (!currentProject) {
      return;
    }

    try {
      const prepared = await prepareDataAsset(currentProject.id, asset.id, {
        docling_do_ocr: options.docling_do_ocr,
        docling_force_ocr: options.docling_force_ocr,
        method: method === "docling" ? "docling" : "pymupdf_text",
        output_format: method === "docling" ? "markdown_json" : "markdown",
        page_breaks: options.page_breaks,
      });
      upsertAsset(prepared);
      setExpandedAssetIds((current) => new Set(current).add(asset.id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to prepare source data");
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
      <header className="page-header action-header">
        <div>
          <p className="eyebrow">Data</p>
          <h1>Data Assets</h1>
          <p>Source data and linked prepared versions for the current project.</p>
        </div>
        <button className="primary-action" onClick={() => setModal("source")} type="button">
          Add Source Data
        </button>
      </header>

      {error ? <div className="notice">Data asset unavailable: {error}</div> : null}

      {sourceAssets.length === 0 ? (
        <div className="empty-state">No source data uploaded for this project yet.</div>
      ) : (
        <div className="asset-list">
          {sourceAssets.map((source) => (
            <SourceAssetCard
              asset={source}
              expanded={expandedAssetIds.has(source.id)}
              key={source.id}
              onAddFiles={handleAddFiles}
              onAddPrepared={openPreparedModal}
              onDeleteAsset={handleDeleteAsset}
              onDeleteFile={handleDeleteFile}
              onPrepare={handlePrepare}
              onToggle={toggleAsset}
              preparationMethods={preparationMethods.length > 0 ? preparationMethods : DEFAULT_PREPARATION_METHODS}
              projectId={currentProject.id}
              preparedAssets={preparedAssets.filter((asset) => asset.parent_id === source.id)}
            />
          ))}
        </div>
      )}

      {modal === "source" ? (
        <SourceUploadModal
          onClose={closeModal}
          onCreated={upsertAsset}
          projectId={currentProject.id}
          setError={setError}
        />
      ) : null}

      {modal === "prepared" && preparedParent ? (
        <PreparedUploadModal
          onClose={closeModal}
          onCreated={upsertAsset}
          parent={preparedParent}
          projectId={currentProject.id}
          setError={setError}
        />
      ) : null}
    </section>
  );
}

function SourceAssetCard({
  asset,
  expanded,
  onAddFiles,
  onAddPrepared,
  onDeleteAsset,
  onDeleteFile,
  onPrepare,
  onToggle,
  preparationMethods,
  projectId,
  preparedAssets,
}: {
  asset: DataAsset;
  expanded: boolean;
  onAddFiles: (asset: DataAsset, files: File[]) => void;
  onAddPrepared: (asset: DataAsset) => void;
  onDeleteAsset: (asset: DataAsset) => void;
  onDeleteFile: (asset: DataAsset, file: DataAssetManifestFile) => void;
  onPrepare: (asset: DataAsset, method: string, options: Record<string, boolean>) => void;
  onToggle: (assetId: string) => void;
  preparationMethods: PreparationMethod[];
  projectId: string;
  preparedAssets: DataAsset[];
}) {
  const files = asset.current_manifest_json?.files ?? [];

  return (
    <article className="asset-card">
      <div className="asset-summary">
        <button className="asset-title" onClick={() => onToggle(asset.id)} type="button">
          <span>{expanded ? "v" : ">"}</span>
          {asset.name}
        </button>
        <span>{asset.data_format}</span>
        <span>{files.length} file(s)</span>
        <span title={asset.manifest_hash ?? undefined}>{shortHash(asset.manifest_hash)}</span>
        <InlineFileAdd asset={asset} onAddFiles={onAddFiles} />
        <button className="text-action danger" onClick={() => onDeleteAsset(asset)} type="button">
          Delete
        </button>
      </div>

      {expanded ? (
        <div className="asset-details">
          <FileList asset={asset} files={files} onDeleteFile={onDeleteFile} projectId={projectId} />
          <PreparedVersionList
            assets={preparedAssets}
            onAddPrepared={() => onAddPrepared(asset)}
            onDeleteAsset={onDeleteAsset}
            onDeleteFile={onDeleteFile}
            onPrepare={(method, options) => onPrepare(asset, method, options)}
            preparationMethods={preparationMethods}
            projectId={projectId}
          />
        </div>
      ) : null}
    </article>
  );
}

function PreparedVersionList({
  assets,
  onAddPrepared,
  onDeleteAsset,
  onDeleteFile,
  onPrepare,
  preparationMethods,
  projectId,
}: {
  assets: DataAsset[];
  onAddPrepared: () => void;
  onDeleteAsset: (asset: DataAsset) => void;
  onDeleteFile: (asset: DataAsset, file: DataAssetManifestFile) => void;
  onPrepare: (method: string, options: Record<string, boolean>) => void;
  preparationMethods: PreparationMethod[];
  projectId: string;
}) {
  return (
    <div className="prepared-list">
      <div className="prepared-actions">
        <h2>Prepared Versions</h2>
        <div>
          <button className="secondary-action" onClick={onAddPrepared} type="button">
            Add Prepared Version
          </button>
          <PrepareControls methods={preparationMethods} onPrepare={onPrepare} />
        </div>
      </div>
      {assets.length === 0 ? <div className="nested-empty">No prepared versions yet.</div> : null}
      {assets.map((asset) => {
        const files = asset.current_manifest_json?.files ?? [];
        const params = asset.preparation_params_json ?? {};
        return (
          <div className="prepared-item" key={asset.id}>
            <div className="prepared-heading">
              <strong>{asset.name}</strong>
              <span>{asset.data_format}</span>
              <span>{String(params.method ?? "-")}</span>
              <span>{String(params.tool ?? "-")}</span>
              <span title={asset.manifest_hash ?? undefined}>{shortHash(asset.manifest_hash)}</span>
              <button className="text-action danger" onClick={() => onDeleteAsset(asset)} type="button">
                Delete
              </button>
            </div>
            <FileList asset={asset} files={files} onDeleteFile={onDeleteFile} projectId={projectId} />
          </div>
        );
      })}
    </div>
  );
}

function PrepareControls({
  methods,
  onPrepare,
}: {
  methods: PreparationMethod[];
  onPrepare: (method: string, options: Record<string, boolean>) => void;
}) {
  const [method, setMethod] = useState(methods[0]?.id ?? "pymupdf_text");
  const [options, setOptions] = useState<Record<string, boolean>>({});
  const selectedMethod = methods.find((item) => item.id === method) ?? methods[0];
  const fields = selectedMethod?.fields ?? [];

  useEffect(() => {
    if (!methods.some((item) => item.id === method)) {
      setMethod(methods[0]?.id ?? "pymupdf_text");
    }
  }, [method, methods]);

  useEffect(() => {
    setOptions(
      Object.fromEntries(
        fields
          .filter((field) => field.type === "boolean")
          .map((field) => [field.name, Boolean(field.default)]),
      ),
    );
  }, [method, fields]);

  return (
    <span className="prepare-controls">
      <label>
        Prepare with
        <select value={method} onChange={(event) => setMethod(event.target.value)}>
          {methods.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      {fields
        .filter((field) => field.type === "boolean")
        .map((field) => (
          <label className="prepare-check" key={field.name} title={field.help_text ?? undefined}>
            <input
              checked={Boolean(options[field.name])}
              onChange={(event) =>
                setOptions((current) => ({ ...current, [field.name]: event.target.checked }))
              }
              type="checkbox"
            />
            {field.label}
          </label>
        ))}
      <button className="secondary-action" onClick={() => onPrepare(method, options)} type="button">
        OK
      </button>
    </span>
  );
}

function FileList({
  asset,
  files,
  onDeleteFile,
  projectId,
}: {
  asset: DataAsset;
  files: DataAssetManifestFile[];
  onDeleteFile: (asset: DataAsset, file: DataAssetManifestFile) => void;
  projectId: string;
}) {
  if (files.length === 0) {
    return <div className="nested-empty">No files in current manifest.</div>;
  }

  return (
    <div className="file-list">
      {files.map((file) => (
        <div className="file-row" key={file.stored_path}>
          <span>
            <a
              className="file-link"
              href={getDataAssetFileDownloadUrl(projectId, asset.id, file.stored_path)}
            >
              {file.original_name}
            </a>
          </span>
          <FileInspectionBadges file={file} />
          <span>{formatBytes(file.size_bytes)}</span>
          <button className="text-action danger" onClick={() => onDeleteFile(asset, file)} type="button">
            Delete
          </button>
        </div>
      ))}
    </div>
  );
}

function FileInspectionBadges({ file }: { file: DataAssetManifestFile }) {
  const inspection = file.inspection;
  if (!inspection) {
    return <span>-</span>;
  }

  if (inspection.status === "failed") {
    return (
      <span className="badge danger" title={inspection.error}>
        Inspect failed
      </span>
    );
  }

  if (inspection.status === "skipped") {
    return (
      <span className="badge muted" title={inspection.reason}>
        {inspection.file_type ?? "file"}
      </span>
    );
  }

  const hasText = inspection.text_layer?.has_text;
  const likelyScanned = inspection.scan_likelihood?.likely_scanned;
  const title = buildInspectionTitle(file);

  return (
    <span className="inspection-badges" title={title}>
      {inspection.file_type ? <span className="badge">{inspection.file_type}</span> : null}
      {inspection.page_count !== undefined ? <span className="badge">{inspection.page_count} pages</span> : null}
      <span className={hasText ? "badge good" : "badge warning"}>
        {hasText ? "Text layer" : "No text"}
      </span>
      {inspection.is_encrypted ? <span className="badge danger">Encrypted</span> : null}
      {likelyScanned === true ? <span className="badge warning">Likely scanned</span> : null}
    </span>
  );
}

function InlineFileAdd({
  asset,
  onAddFiles,
}: {
  asset: DataAsset;
  onAddFiles: (asset: DataAsset, files: File[]) => void;
}) {
  return (
    <label className="inline-upload">
      Add files
      <input
        multiple
        onChange={(event) => {
          onAddFiles(asset, Array.from(event.target.files ?? []));
          event.currentTarget.value = "";
        }}
        type="file"
      />
    </label>
  );
}

function SourceUploadModal({
  onClose,
  onCreated,
  projectId,
  setError,
}: {
  onClose: () => void;
  onCreated: (asset: DataAsset) => void;
  projectId: string;
  setError: (error: string | null) => void;
}) {
  const [name, setName] = useState("");
  const [format, setFormat] = useState("pdf");
  const [files, setFiles] = useState<File[]>([]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || files.length === 0) {
      return;
    }

    try {
      const asset = await uploadRawDataAsset(projectId, {
        data_format: format,
        files,
        name: name.trim(),
      });
      onCreated(asset);
      setError(null);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload source data");
    }
  }

  return (
    <Modal onClose={onClose} title="Add Source Data">
      <form className="modal-form" onSubmit={handleSubmit}>
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Source format
          <select value={format} onChange={(event) => setFormat(event.target.value)}>
            <option value="pdf">pdf</option>
            <option value="markdown">markdown</option>
            <option value="text">text</option>
            <option value="docx">docx</option>
            <option value="html">html</option>
            <option value="mixed">mixed</option>
            <option value="other">other</option>
          </select>
        </label>
        <label>
          Files
          <input multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} type="file" />
        </label>
        <button disabled={files.length === 0} type="submit">
          Upload Source Data
        </button>
      </form>
    </Modal>
  );
}

function PreparedUploadModal({
  onClose,
  onCreated,
  parent,
  projectId,
  setError,
}: {
  onClose: () => void;
  onCreated: (asset: DataAsset) => void;
  parent: DataAsset;
  projectId: string;
  setError: (error: string | null) => void;
}) {
  const [name, setName] = useState(`${parent.name} prepared`);
  const [format, setFormat] = useState("markdown");
  const [method, setMethod] = useState("external_gpu");
  const [tool, setTool] = useState("marker");
  const [toolVersion, setToolVersion] = useState("");
  const [command, setCommand] = useState("");
  const [ocr, setOcr] = useState(false);
  const [layout, setLayout] = useState(true);
  const [notes, setNotes] = useState("Prepared outside RAG Lab and uploaded.");
  const [files, setFiles] = useState<File[]>([]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || files.length === 0) {
      return;
    }

    try {
      const asset = await uploadPreparedDataAsset(projectId, {
        data_format: format,
        files,
        name: name.trim(),
        parent_id: parent.id,
        preparation_params_json: {
          command,
          method,
          notes,
          output_format: format,
          settings: { layout, ocr },
          source_format: parent.data_format,
          tool,
          tool_version: toolVersion,
        },
      });
      onCreated(asset);
      setError(null);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload prepared data");
    }
  }

  return (
    <Modal onClose={onClose} title={`Add Prepared Version for ${parent.name}`}>
      <form className="modal-form two-column" onSubmit={handleSubmit}>
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Output format
          <select value={format} onChange={(event) => setFormat(event.target.value)}>
            <option value="markdown">markdown</option>
            <option value="text">text</option>
            <option value="jsonl">jsonl</option>
            <option value="mixed">mixed</option>
            <option value="other">other</option>
          </select>
        </label>
        <label>
          Method
          <select value={method} onChange={(event) => setMethod(event.target.value)}>
            <option value="external_gpu">external_gpu</option>
            <option value="pymupdf_text">pymupdf_text</option>
            <option value="docling">docling</option>
            <option value="marker">marker</option>
            <option value="mineru">mineru</option>
            <option value="custom_vlm">custom_vlm</option>
            <option value="manual">manual</option>
          </select>
        </label>
        <label>
          Tool
          <input value={tool} onChange={(event) => setTool(event.target.value)} />
        </label>
        <label>
          Tool version
          <input value={toolVersion} onChange={(event) => setToolVersion(event.target.value)} />
        </label>
        <label>
          Command
          <input value={command} onChange={(event) => setCommand(event.target.value)} />
        </label>
        <label className="check-row">
          <input checked={ocr} onChange={(event) => setOcr(event.target.checked)} type="checkbox" />
          OCR enabled
        </label>
        <label className="check-row">
          <input checked={layout} onChange={(event) => setLayout(event.target.checked)} type="checkbox" />
          Layout enabled
        </label>
        <label className="wide-field">
          Notes
          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} />
        </label>
        <label className="wide-field">
          Files
          <input multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} type="file" />
        </label>
        <button disabled={files.length === 0} type="submit">
          Upload Prepared Version
        </button>
      </form>
    </Modal>
  );
}

function Modal({
  children,
  onClose,
  title,
}: {
  children: ReactNode;
  onClose: () => void;
  title: string;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <div aria-modal="true" className="modal-panel" role="dialog">
        <header className="modal-header">
          <h2>{title}</h2>
          <button className="text-action" onClick={onClose} type="button">
            Close
          </button>
        </header>
        {children}
      </div>
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

function shortHash(hash?: string | null) {
  return hash ? hash.replace("sha256:", "").slice(0, 12) : "-";
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function buildInspectionTitle(file: DataAssetManifestFile) {
  const inspection = file.inspection;
  if (!inspection) {
    return "";
  }

  const lines = [
    `Type: ${inspection.file_type ?? "unknown"}`,
    inspection.page_count !== undefined ? `Pages: ${inspection.page_count}` : null,
    inspection.text_layer
      ? `Text pages: ${inspection.text_layer.pages_with_text}, chars: ${inspection.text_layer.text_char_count}`
      : null,
    inspection.images
      ? `Images: ${inspection.images.image_count}, pages with images: ${inspection.images.pages_with_images}`
      : null,
    inspection.scan_likelihood ? `Scan signal: ${inspection.scan_likelihood.reason}` : null,
  ].filter(Boolean);

  return lines.join("\n");
}
