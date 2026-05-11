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

export async function getHealth(): Promise<{ status: string }> {
  return request("/health");
}

export async function listProjects(): Promise<{ projects: Project[] }> {
  return request("/projects");
}

export async function createProject(payload: ProjectCreate): Promise<Project> {
  return request("/projects", {
    body: JSON.stringify(payload),
    method: "POST",
  });
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
