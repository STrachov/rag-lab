const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8080/v1";

export type Dataset = {
  dataset_id: string;
  name: string;
  description?: string | null;
  domain?: string | null;
  document_count: number;
  created_at: string;
  metadata: Record<string, unknown>;
};

export async function getHealth(): Promise<{ status: string }> {
  return request("/health");
}

export async function listDatasets(): Promise<{ datasets: Dataset[] }> {
  return request("/datasets");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}
