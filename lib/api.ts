const RAW_API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";
export const API = RAW_API.replace(/\/+$/, "");

export class ApiRequestError extends Error {
  status: number;
  type?: string;
  requestId?: string;
  constructor(message: string, status = 0, type?: string, requestId?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.type = type;
    this.requestId = requestId;
  }
}

async function parseError(response: Response): Promise<ApiRequestError> {
  const requestId = response.headers.get("x-request-id") || undefined;
  let data: any = null;
  try { data = await response.clone().json(); } catch {}
  const detail = data?.detail;
  const message =
    (typeof detail === "string" && detail) ||
    detail?.message ||
    data?.message ||
    (response.status === 401 ? "Your session has expired. Please sign in again." :
      response.status === 403 ? "You do not have permission to perform this action." :
      response.status === 404 ? "The requested Rivu resource was not found." :
      response.status >= 500 ? "Rivu's backend returned a server error. Please retry." :
      "Rivu could not complete this request.");
  return new ApiRequestError(String(message), response.status, detail?.type || data?.type, requestId);
}

export async function authFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  const access = typeof window !== "undefined" ? localStorage.getItem("rivu_access_token") : null;
  if (access) headers.set("Authorization", "Bearer " + access);

  let response: Response;
  try {
    response = await fetch(API + path, { ...init, headers });
  } catch {
    throw new ApiRequestError(
      "Unable to reach the Rivu backend. The service may be waking from inactivity or your connection may be offline.",
      0,
      "network_error"
    );
  }

  if (response.status !== 401 || typeof window === "undefined") return response;

  const refresh = localStorage.getItem("rivu_refresh_token");
  if (!refresh) return response;

  let refreshResponse: Response;
  try {
    refreshResponse = await fetch(API + "/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
  } catch {
    return response;
  }
  if (!refreshResponse.ok) {
    localStorage.removeItem("rivu_access_token");
    localStorage.removeItem("rivu_refresh_token");
    return response;
  }

  const data = await refreshResponse.json();
  localStorage.setItem("rivu_access_token", data.tokens.access_token);
  localStorage.setItem("rivu_refresh_token", data.tokens.refresh_token);

  const retryHeaders = new Headers(init.headers);
  retryHeaders.set("Authorization", "Bearer " + data.tokens.access_token);
  try {
    return await fetch(API + path, { ...init, headers: retryHeaders });
  } catch {
    throw new ApiRequestError("The Rivu backend could not be reached after refreshing your session.", 0, "network_error");
  }
}

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authFetch(path, init);
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<T>;
}

export async function requestBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const response = await authFetch(path, init);
  if (!response.ok) throw await parseError(response);
  return response.blob();
}
