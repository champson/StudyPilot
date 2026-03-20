import type { SuccessResponse, ErrorResponse } from "@/types/api";

import { env } from "./env";

const API_BASE = env.NEXT_PUBLIC_API_BASE;

/** Keys stored in localStorage for auth state — shared with auth.ts */
export const AUTH_STORAGE_KEYS = [
  "access_token", "user_role", "user_name", "student_id",
  "onboarding_completed", "onboarding_draft",
] as const;

class ApiError extends Error {
  code: string;
  detail: Record<string, unknown>;

  constructor(err: ErrorResponse["error"]) {
    super(err.message);
    this.code = err.code;
    this.detail = err.detail;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function clearAuthAndRedirect() {
  if (typeof window === "undefined") return;
  for (const key of AUTH_STORAGE_KEYS) localStorage.removeItem(key);
  window.location.href = "/login";
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({
      error: { code: "NETWORK_ERROR", message: "网络请求失败", detail: {} },
    }));

    if (res.status === 401) {
      // Don't clear auth for login endpoints — surface the real error
      const isLoginRequest = path.startsWith("/auth/token-login")
        || path.startsWith("/auth/admin-login");
      if (!isLoginRequest) {
        clearAuthAndRedirect();
      }
      throw new ApiError(
        body.error || { code: "UNAUTHORIZED", message: "登录已过期", detail: {} }
      );
    }

    throw new ApiError(body.error);
  }

  if (res.status === 204) return undefined as T;

  const json: SuccessResponse<T> = await res.json();
  return json.data;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export { ApiError };
