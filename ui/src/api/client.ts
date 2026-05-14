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
  role?: string;
  sha256: string;
  size_bytes: number;
  stored_path: string;
  source?: {
    original_name?: string;
    stored_path?: string;
  };
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
  method?: "pymupdf_text" | "docling";
  settings?: Record<string, unknown>;
};

export type PreparationMethodField = {
  name: string;
  label: string;
  type: "boolean" | "select" | "text";
  default: boolean | string;
  help_text?: string | null;
  options?: Array<{ label: string; value: string }> | null;
};

export type PreparationMethod = {
  id: "pymupdf_text" | "docling" | string;
  label: string;
  description: string;
  output_formats: string[];
  fields: PreparationMethodField[];
};

export type ParameterSet = {
  id: string;
  project_id: string;
  name: string;
  description?: string | null;
  category: string;
  params_json: Record<string, unknown>;
  params_hash: string;
  created_at: string;
};

export type ParameterSetCreate = {
  name: string;
  description?: string;
  category?: string;
  params_json: Record<string, unknown>;
  params_hash: string;
};

export type ParameterSetDeleteResponse = {
  deleted_parameter_set_id: string;
};

export type ChunkingParamValue = string | number | boolean;

export type ChunkingParams = {
  strategy: string;
  params: Record<string, ChunkingParamValue>;
};

export type ChunkingStrategyField = {
  name: string;
  label: string;
  type: "number" | "select" | "boolean" | "text";
  default: ChunkingParamValue;
  help_text?: string | null;
  min?: number | null;
  max?: number | null;
  options?: Array<{ label: string; value: string }> | null;
};

export type ChunkingStrategy = {
  id: string;
  label: string;
  description: string;
  default_params: Record<string, ChunkingParamValue>;
  fields: ChunkingStrategyField[];
};

export type ChunkingPreviewRequest = {
  data_asset_id: string;
  chunking: ChunkingParams;
  max_chunks?: number;
  text_preview_chars?: number;
};

export type ChunkPreview = {
  chunk_id: string;
  source_name: string;
  stored_path: string;
  section?: string | null;
  heading_path: string[];
  page?: number | null;
  token_count: number;
  char_count: number;
  text_preview: string;
};

export type ChunkingPreviewSummary = {
  chunk_count: number;
  files_count: number;
  min_tokens: number;
  avg_tokens: number;
  max_tokens: number;
  min_chars: number;
  avg_chars: number;
  max_chars: number;
  chunks_by_file: Array<{ source_name: string; chunk_count: number }>;
  token_counter: string;
};

export type ChunkingPreviewResponse = {
  summary: ChunkingPreviewSummary;
  warnings: string[];
  chunks: ChunkPreview[];
};

export type DerivedCache = {
  id: string;
  project_id: string;
  data_asset_id?: string | null;
  params_hash: string;
  cache_type: "chunks" | "embeddings" | "qdrant_index" | "retrieval_temp" | "answer_temp";
  cache_key: string;
  status: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  last_used_at?: string | null;
};

export type DerivedCacheListResponse = {
  derived_caches: DerivedCache[];
};

export type EmbeddingParamValue = string | number | boolean;

export type EmbeddingModelField = {
  name: string;
  label: string;
  type: "number" | "select" | "boolean" | "text";
  default: EmbeddingParamValue;
  help_text?: string | null;
  min?: number | null;
  max?: number | null;
  step?: number | null;
  options?: Array<{ label: string; value: string }> | null;
};

export type EmbeddingModel = {
  id: string;
  label: string;
  description: string;
  provider: string;
  model_name: string;
  vector_size: number;
  default_params: Record<string, EmbeddingParamValue>;
  fields: EmbeddingModelField[];
};

export type SparseModelField = {
  name: string;
  label: string;
  type: "number" | "select" | "boolean" | "text";
  default: EmbeddingParamValue;
  help_text?: string | null;
  min?: number | null;
  max?: number | null;
  step?: number | null;
};

export type SparseModel = {
  id: string;
  label: string;
  description: string;
  provider: string;
  default_params: Record<string, EmbeddingParamValue>;
  fields: SparseModelField[];
};

export type RerankerModelField = {
  name: string;
  label: string;
  type: "number" | "select" | "boolean" | "text";
  default: EmbeddingParamValue;
  help_text?: string | null;
  min?: number | null;
  max?: number | null;
  step?: number | null;
  options?: Array<{ label: string; value: string }> | null;
};

export type RerankerModel = {
  id: string;
  label: string;
  description: string;
  provider: string;
  model_name: string;
  backend: string;
  default_params: Record<string, EmbeddingParamValue>;
  fields: RerankerModelField[];
};

export type QdrantIndexRequest = {
  chunks_cache_id: string;
  embedding: {
    model_id: string;
    params: Record<string, EmbeddingParamValue>;
  };
  sparse?: {
    model_id: string;
    params: Record<string, EmbeddingParamValue>;
  } | null;
  index_mode?: "dense" | "sparse" | "hybrid";
  collection_name?: string | null;
  distance?: "Cosine" | "Dot" | "Euclid";
};

export type RetrievedChunk = {
  chunk_id?: string | null;
  score?: number | null;
  dense_score?: number | null;
  sparse_score?: number | null;
  rerank_score?: number | null;
  original_score?: number | null;
  original_rank?: number | null;
  source_name?: string | null;
  stored_path?: string | null;
  section?: string | null;
  heading_path?: string[];
  page?: number | null;
  token_count?: number | null;
  char_count?: number | null;
  text_preview?: string | null;
};

export type RetrievalPreviewResponse = {
  index_cache_id: string;
  retrieval_cache_id?: string | null;
  mode: "dense" | "sparse" | "hybrid";
  query: string;
  top_k: number;
  candidate_k?: number | null;
  reranking?: Record<string, unknown> | null;
  retrieved_chunks: RetrievedChunk[];
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

export async function listPreparationMethods(
  projectId: string,
): Promise<{ methods: PreparationMethod[] }> {
  return request(`/projects/${projectId}/data-assets/preparation/methods`);
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

export async function deleteParameterSet(
  projectId: string,
  parameterSetId: string,
): Promise<ParameterSetDeleteResponse> {
  return request(`/projects/${projectId}/parameter-sets/${parameterSetId}`, {
    method: "DELETE",
  });
}

export async function previewChunking(
  projectId: string,
  payload: ChunkingPreviewRequest,
): Promise<ChunkingPreviewResponse> {
  return request(`/projects/${projectId}/parameter-sets/chunking/preview`, {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export async function listChunkingStrategies(
  projectId: string,
): Promise<{ strategies: ChunkingStrategy[] }> {
  return request(`/projects/${projectId}/parameter-sets/chunking/strategies`);
}

export async function materializeChunks(
  projectId: string,
  payload: ChunkingPreviewRequest,
): Promise<DerivedCache> {
  return request(`/projects/${projectId}/chunks/materialize`, {
    body: JSON.stringify({
      chunking: payload.chunking,
      data_asset_id: payload.data_asset_id,
    }),
    method: "POST",
  });
}

export async function downloadGroundTruthAuthoringPack(
  projectId: string,
  chunksCacheId: string,
): Promise<Blob> {
  return requestBlob(`/projects/${projectId}/chunks/${chunksCacheId}/gt-authoring-pack`);
}

export async function listEmbeddingModels(
  projectId: string,
): Promise<{ models: EmbeddingModel[] }> {
  return request(`/projects/${projectId}/embedding/models`);
}

export async function listSparseModels(
  projectId: string,
): Promise<{ models: SparseModel[] }> {
  return request(`/projects/${projectId}/sparse/models`);
}

export async function listRerankerModels(
  projectId: string,
): Promise<{ models: RerankerModel[] }> {
  return request(`/projects/${projectId}/reranking/models`);
}

export async function listDerivedCaches(
  projectId: string,
  cacheType?: DerivedCache["cache_type"],
): Promise<DerivedCacheListResponse> {
  const params = cacheType ? `?${new URLSearchParams({ cache_type: cacheType }).toString()}` : "";
  return request(`/projects/${projectId}/derived-cache${params}`);
}

export async function createQdrantIndex(
  projectId: string,
  payload: QdrantIndexRequest,
): Promise<DerivedCache> {
  return request(`/projects/${projectId}/indexes/qdrant`, {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export async function previewRetrieval(
  projectId: string,
  payload: {
    candidate_k?: number | null;
    index_cache_id: string;
    mode?: "dense" | "sparse" | "hybrid";
    query: string;
    top_k?: number;
  },
): Promise<RetrievalPreviewResponse> {
  return request(`/projects/${projectId}/retrieve/preview`, {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export async function previewRerank(
  projectId: string,
  payload: {
    retrieval_cache_id: string;
    reranking: {
      enabled: boolean;
      model_id: string;
      params: Record<string, EmbeddingParamValue>;
    };
    top_k?: number;
  },
): Promise<RetrievalPreviewResponse> {
  return request(`/projects/${projectId}/rerank/preview`, {
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
    throw new Error(await responseErrorMessage(response));
  }

  return response.json() as Promise<T>;
}

async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.blob();
}

async function responseErrorMessage(response: Response): Promise<string> {
  const fallback = `API request failed: ${response.status} ${response.statusText}`;
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return fallback;
  }
  try {
    const payload = (await response.json()) as { detail?: unknown; error?: { message?: unknown } };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (typeof payload.error?.message === "string") {
      return payload.error.message;
    }
  } catch {
    return fallback;
  }
  return fallback;
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
