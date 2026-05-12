const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8080/v1";

export type Project = {
  id: string;
  name: string;
  description?: string | null;
  domain?: string | null;
  status: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ProjectCreate = {
  name: string;
  description?: string;
  domain?: string;
  status?: string;
  metadata_json?: Record<string, unknown>;
};

export type DataAsset = {
  id: string;
  project_id: string;
  name: string;
  asset_type: "raw" | "prepared";
  data_format: string;
  storage_kind: string;
  parent_id?: string | null;
  storage_path?: string | null;
  manifest_hash?: string | null;
  preparation_params_json?: Record<string, unknown> | null;
  metadata_json: Record<string, unknown>;
  status: string;
  created_at: string;
  current_manifest_json?: DataAssetManifest | null;
};

export type DataAssetCreate = {
  name: string;
  asset_type?: "raw" | "prepared";
  data_format?: string;
  storage_kind?: string;
  parent_id?: string | null;
  storage_path?: string | null;
  manifest_hash?: string | null;
  preparation_params_json?: Record<string, unknown> | null;
  metadata_json?: Record<string, unknown>;
  status?: string;
};

export type RawDataAssetUpload = {
  name: string;
  data_format: string;
  files: File[];
  metadata_json?: Record<string, unknown>;
};

export type PreparedDataAssetUpload = {
  name: string;
  data_format: string;
  files: File[];
  parent_id?: string;
  preparation_params_json: Record<string, unknown>;
  metadata_json?: Record<string, unknown>;
};

export type DataAssetManifestFile = {
  content_type?: string | null;
  inspection?: FileInspection;
  original_name: string;
  sha256: string;
  size_bytes: number;
  stored_path: string;
};

export type FileInspection = {
  error?: string;
  file_type?: string;
  images?: {
    image_count: number;
    pages_with_images: number;
  };
  is_encrypted?: boolean;
  metadata?: Record<string, string>;
  page_count?: number;
  reason?: string;
  scan_likelihood?: {
    likely_scanned: boolean | null;
    reason: string;
  };
  status: "ok" | "failed" | "skipped";
  text_layer?: {
    avg_text_chars_per_page: number;
    has_text: boolean;
    pages_with_text: number;
    text_char_count: number;
    text_pages_ratio: number;
  };
};

export type DataAssetManifest = {
  asset_id: string;
  asset_type: "raw" | "prepared";
  files: DataAssetManifestFile[];
  manifest_hash?: string;
  parent_id?: string;
  preparation_params_json?: Record<string, unknown>;
  project_id: string;
};

export type DataAssetFileDeleteResponse = {
  data_asset?: DataAsset | null;
  deleted_data_asset_id?: string | null;
};

export type DataAssetDeleteResponse = {
  deleted_data_asset_ids: string[];
};

export type DataAssetPrepareRequest = {
  name?: string;
  method?: "pymupdf_text";
  output_format?: "markdown";
  page_breaks?: boolean;
};

export type ParameterSet = {
  id: string;
  project_id: string;
  name: string;
  description?: string | null;
  params_json: Record<string, unknown>;
  params_hash: string;
  created_at: string;
};

export type ParameterSetCreate = {
  name: string;
  description?: string;
  params_json: Record<string, unknown>;
  params_hash: string;
};

export type GroundTruthSet = {
  id: string;
  project_id: string;
  name: string;
  data_asset_id?: string | null;
  storage_path?: string | null;
  manifest_hash?: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type GroundTruthSetCreate = {
  name: string;
  data_asset_id?: string | null;
  storage_path?: string | null;
  manifest_hash?: string | null;
  metadata_json?: Record<string, unknown>;
};

export type SavedExperiment = {
  id: string;
  project_id: string;
  name: string;
  data_asset_id: string;
  ground_truth_set_id?: string | null;
  parameter_set_id?: string | null;
  params_snapshot_json: Record<string, unknown>;
  params_hash: string;
  metrics_summary_json: Record<string, unknown>;
  status: string;
  notes?: string | null;
  debug_level: "none" | "summary" | "full";
  code_commit?: string | null;
  pipeline_version?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_json?: Record<string, unknown> | null;
};

export async function getHealth(): Promise<{ status: string }> {
  return request("/health");
}

export async function listProjects(): Promise<{ projects: Project[] }> {
  return request("/projects");
}

export async function getProject(projectId: string): Promise<Project> {
  return request(`/projects/${projectId}`);
}

export async function createProject(payload: ProjectCreate): Promise<Project> {
  return request("/projects", {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export async function listDataAssets(projectId: string): Promise<{ data_assets: DataAsset[] }> {
  return request(`/projects/${projectId}/data-assets`);
}

export async function createDataAsset(
  projectId: string,
  payload: DataAssetCreate,
): Promise<DataAsset> {
  return request(`/projects/${projectId}/data-assets`, {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export async function uploadRawDataAsset(
  projectId: string,
  payload: RawDataAssetUpload,
): Promise<DataAsset> {
  const formData = new FormData();
  formData.append("name", payload.name);
  formData.append("data_format", payload.data_format);
  if (payload.metadata_json) {
    formData.append("metadata_json", JSON.stringify(payload.metadata_json));
  }
  appendFiles(formData, payload.files);

  return request(`/projects/${projectId}/data-assets/raw/upload`, {
    body: formData,
    method: "POST",
  });
}

export async function uploadPreparedDataAsset(
  projectId: string,
  payload: PreparedDataAssetUpload,
): Promise<DataAsset> {
  const formData = new FormData();
  formData.append("name", payload.name);
  formData.append("data_format", payload.data_format);
  formData.append("preparation_params_json", JSON.stringify(payload.preparation_params_json));
  if (payload.parent_id) {
    formData.append("parent_id", payload.parent_id);
  }
  if (payload.metadata_json) {
    formData.append("metadata_json", JSON.stringify(payload.metadata_json));
  }
  appendFiles(formData, payload.files);

  return request(`/projects/${projectId}/data-assets/prepared/upload`, {
    body: formData,
    method: "POST",
  });
}

export async function addDataAssetFiles(
  projectId: string,
  dataAssetId: string,
  files: File[],
): Promise<DataAsset> {
  const formData = new FormData();
  appendFiles(formData, files);

  return request(`/projects/${projectId}/data-assets/${dataAssetId}/files`, {
    body: formData,
    method: "POST",
  });
}

export async function deleteDataAssetFile(
  projectId: string,
  dataAssetId: string,
  storedPath: string,
): Promise<DataAssetFileDeleteResponse> {
  const params = new URLSearchParams({ stored_path: storedPath });
  return request(`/projects/${projectId}/data-assets/${dataAssetId}/files?${params.toString()}`, {
    method: "DELETE",
  });
}

export async function deleteDataAsset(
  projectId: string,
  dataAssetId: string,
): Promise<DataAssetDeleteResponse> {
  return request(`/projects/${projectId}/data-assets/${dataAssetId}`, {
    method: "DELETE",
  });
}

export async function prepareDataAsset(
  projectId: string,
  dataAssetId: string,
  payload: DataAssetPrepareRequest = {},
): Promise<DataAsset> {
  return request(`/projects/${projectId}/data-assets/${dataAssetId}/prepare`, {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export function getDataAssetFileDownloadUrl(
  projectId: string,
  dataAssetId: string,
  storedPath: string,
): string {
  const params = new URLSearchParams({ stored_path: storedPath });
  return `${API_BASE_URL}/projects/${projectId}/data-assets/${dataAssetId}/files/download?${params.toString()}`;
}

export async function listParameterSets(
  projectId: string,
): Promise<{ parameter_sets: ParameterSet[] }> {
  return request(`/projects/${projectId}/parameter-sets`);
}

export async function createParameterSet(
  projectId: string,
  payload: ParameterSetCreate,
): Promise<ParameterSet> {
  return request(`/projects/${projectId}/parameter-sets`, {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export async function listGroundTruthSets(
  projectId: string,
): Promise<{ ground_truth_sets: GroundTruthSet[] }> {
  return request(`/projects/${projectId}/ground-truth-sets`);
}

export async function createGroundTruthSet(
  projectId: string,
  payload: GroundTruthSetCreate,
): Promise<GroundTruthSet> {
  return request(`/projects/${projectId}/ground-truth-sets`, {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export async function listSavedExperiments(
  projectId: string,
): Promise<{ saved_experiments: SavedExperiment[] }> {
  return request(`/projects/${projectId}/saved-experiments`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers =
    init?.body instanceof FormData
      ? init?.headers
      : { "Content-Type": "application/json", ...init?.headers };
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers,
    ...init,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

function appendFiles(formData: FormData, files: File[]) {
  files.forEach((file) => {
    const relativePath = getRelativePath(file);
    formData.append("files", file, relativePath);
  });
}

function getRelativePath(file: File): string {
  const maybeRelativeFile = file as File & { webkitRelativePath?: string };
  return maybeRelativeFile.webkitRelativePath || file.name;
}
