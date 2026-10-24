const rawApi = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";
const API = rawApi.replace(/\/+$/, "").endsWith("/api/v1")
  ? rawApi.replace(/\/+$/, "")
  : `${rawApi.replace(/\/+$/, "")}/api/v1`;

export function extractErrorMessage(data: unknown, fallback = "An unexpected error occurred."): string {
  if (!data) return fallback;
  if (typeof data === "string") return data;
  if (typeof data === "object") {
    const obj = data as Record<string, unknown>;
    if (typeof obj.detail === "string") return obj.detail;
    if (obj.detail && typeof obj.detail === "object") {
      const detailObj = obj.detail as Record<string, unknown>;
      if (typeof detailObj.message === "string") return detailObj.message;
      if (Array.isArray(obj.detail) && obj.detail.length > 0) {
        const first = obj.detail[0] as Record<string, unknown>;
        if (typeof first?.msg === "string") {
          return first.msg.replace(/^Value error,\s*/i, "");
        }
        if (typeof first?.message === "string") return first.message;
      }
    }
    if (typeof obj.message === "string") return obj.message;
  }
  return fallback;
}

export async function authFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  const access = typeof window !== "undefined" ? localStorage.getItem("rivu_access_token") : null;
  if (access) headers.set("Authorization", "Bearer " + access);

  let response = await fetch(API + path, { ...init, headers });
  if (response.status !== 401 || typeof window === "undefined") return response;

  const refresh = localStorage.getItem("rivu_refresh_token");
  if (!refresh) return response;

  const refreshResponse = await fetch(API + "/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
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
  response = await fetch(API + path, { ...init, headers: retryHeaders });
  return response;
}

export { API };

