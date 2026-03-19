import type { SuccessResponse, ErrorResponse } from "@/types/api";

import { env } from "./env";

const API_BASE = env.NEXT_PUBLIC_API_BASE;

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
