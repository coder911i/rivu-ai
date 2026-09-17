const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

export type AuthResponse = {
  user: { id: string; email: string; username: string; full_name?: string; status: string };
  organization: { id: string; name: string; slug: string };
  tokens: { access_token: string; refresh_token: string; token_type: string; expires_in: number };
};

export type Project = {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  color?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  dataset_count: number;
};

function token() { return typeof window === "undefined" ? "" : localStorage.getItem("rivu_access_token") || ""; }

export function saveSession(data: AuthResponse) {
  localStorage.setItem("rivu_access_token", data.tokens.access_token);
  localStorage.setItem("rivu_refresh_token", data.tokens.refresh_token);
  localStorage.setItem("rivu_user", JSON.stringify(data.user));
  localStorage.setItem("rivu_org", JSON.stringify(data.organization));
}

export function clearSession() {
  localStorage.removeItem("rivu_access_token");
  localStorage.removeItem("rivu_refresh_token");
  localStorage.removeItem("rivu_user");
  localStorage.removeItem("rivu_org");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) headers.set("Content-Type", "application/json");
  const access = token();
  if (access) headers.set("Authorization", `Bearer ${access}`);
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : body.detail?.message || "Request failed");
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  signup: (body: { email: string; username: string; password: string; full_name?: string }) => request<AuthResponse>("/auth/signup", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) => request<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => request<any>("/auth/me"),
  projects: () => request<{ projects: Project[]; total: number }>("/projects"),
  createProject: (body: { name: string; description?: string; color?: string; tags?: string[] }) => request<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),
  project: (id: string) => request<any>(`/projects/${id}`),
  upload: (projectId: string, file: File, name?: string) => {
    const form = new FormData(); form.append("file", file); if (name) form.append("name", name);
    return request<any>(`/datasets/projects/${projectId}/upload`, { method: "POST", body: form });
  },
};
