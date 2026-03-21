import type { SuccessResponse, ErrorResponse, RefreshTokenResponse } from "@/types/api";
import { setTokenCookie } from "./auth";

import { env } from "./env";

const API_BASE = env.NEXT_PUBLIC_API_BASE;

/** Common error codes from the backend */
export const ERROR_CODES = {
  // Auth
  AUTH_INVALID_TOKEN: 'AUTH_INVALID_TOKEN',
  AUTH_TOKEN_EXPIRED: 'AUTH_TOKEN_EXPIRED',
  AUTH_INSUFFICIENT_ROLE: 'AUTH_INSUFFICIENT_ROLE',
  AUTH_SHARE_TOKEN_EXPIRED: 'AUTH_SHARE_TOKEN_EXPIRED',
  AUTH_SHARE_TOKEN_INVALID: 'AUTH_SHARE_TOKEN_INVALID',
  AUTH_REFRESH_NOT_ALLOWED: 'AUTH_REFRESH_NOT_ALLOWED',
  // Onboarding
  ONBOARDING_NOT_COMPLETED: 'ONBOARDING_NOT_COMPLETED',
  ONBOARDING_ALREADY_COMPLETED: 'ONBOARDING_ALREADY_COMPLETED',
  // Plan
  PLAN_GENERATION_FAILED: 'PLAN_GENERATION_FAILED',
  PLAN_NOT_FOUND: 'PLAN_NOT_FOUND',
  PLAN_TASK_NOT_FOUND: 'PLAN_TASK_NOT_FOUND',
  PLAN_INVALID_STATUS_TRANSITION: 'PLAN_INVALID_STATUS_TRANSITION',
  // QA
  QA_SESSION_CLOSED: 'QA_SESSION_CLOSED',
  QA_SESSION_NOT_FOUND: 'QA_SESSION_NOT_FOUND',
  QA_LLM_UNAVAILABLE: 'QA_LLM_UNAVAILABLE',
  // Upload
  UPLOAD_FILE_TOO_LARGE: 'UPLOAD_FILE_TOO_LARGE',
  UPLOAD_UNSUPPORTED_FORMAT: 'UPLOAD_UNSUPPORTED_FORMAT',
  UPLOAD_NOT_FOUND: 'UPLOAD_NOT_FOUND',
  // Error Book
  ERROR_BOOK_ITEM_NOT_FOUND: 'ERROR_BOOK_ITEM_NOT_FOUND',
  // System
  REQUEST_TIMEOUT: 'REQUEST_TIMEOUT',
  NETWORK_ERROR: 'NETWORK_ERROR',
} as const;

/** Keys stored in localStorage for auth state — shared with auth.ts */
export const AUTH_STORAGE_KEYS = [
  "access_token", "user_role", "user_name", "student_id",
  "onboarding_completed", "onboarding_draft",
] as const;

// --- Token refresh configuration ---
const STUDENT_REFRESH_THRESHOLD_DAYS = 7;
const ADMIN_REFRESH_THRESHOLD_HOURS = 2;

// --- Anti-concurrent refresh lock ---
let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

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

/**
 * Decode JWT payload without signature verification.
 * Edge Runtime compatible (no Node.js crypto modules).
 */
function decodeJWTPayload(token: string): { sub: string; role: string; exp: number } | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;

    const payload = parts[1];
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const decoded = atob(padded);
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

/**
 * Get token expiry timestamp (Unix seconds)
 */
export function getTokenExpiry(token: string): number | null {
  const payload = decodeJWTPayload(token);
  return payload?.exp ?? null;
}

/**
 * Get user role from token
 */
function getTokenRole(token: string): string | null {
  const payload = decodeJWTPayload(token);
  return payload?.role ?? null;
}

/**
 * Check if token needs refresh based on role-specific thresholds
 */
function shouldRefreshToken(token: string): boolean {
  const exp = getTokenExpiry(token);
  if (!exp) return false;
  
  const role = getTokenRole(token);
  const now = Math.floor(Date.now() / 1000);
  const remainingSeconds = exp - now;
  
  if (remainingSeconds <= 0) return false; // Already expired
  
  // Admin: refresh if <2 hours remaining
  if (role === "admin") {
    return remainingSeconds < ADMIN_REFRESH_THRESHOLD_HOURS * 60 * 60;
  }
  
  // Student/Parent: refresh if <7 days remaining
  return remainingSeconds < STUDENT_REFRESH_THRESHOLD_DAYS * 24 * 60 * 60;
}

/**
 * Update token in both localStorage and cookie
 */
function updateStoredToken(newToken: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("access_token", newToken);
  setTokenCookie(newToken);
}

/**
 * Try to refresh the access token.
 * Returns the new token on success, null on failure.
 * Includes anti-concurrent refresh lock.
 */
async function tryRefreshToken(): Promise<string | null> {
  // If already refreshing, wait for the existing promise
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }
  
  const token = getToken();
  if (!token) return null;
  
  isRefreshing = true;
  
  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({}),
      });
      
      if (!res.ok) {
        // Refresh failed (not in refresh window, expired, etc.)
        return null;
      }
      
      const json: SuccessResponse<RefreshTokenResponse> = await res.json();
      const newToken = json.data.access_token;
      
      // Update stored token
      updateStoredToken(newToken);
      
      return newToken;
    } catch {
      // Network error or other failure, silently ignore
      return null;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();
  
  return refreshPromise;
}

function clearAuthAndRedirect() {
  if (typeof window === "undefined") return;
  for (const key of AUTH_STORAGE_KEYS) localStorage.removeItem(key);
  window.location.href = "/login";
}

/** Default timeout in milliseconds */
const DEFAULT_TIMEOUT = 30000; // 30 seconds

interface RequestOptions extends Omit<RequestInit, 'signal'> {
  timeout?: number;
}

interface InternalRequestOptions extends RequestOptions {
  _retried?: boolean; // Internal flag to prevent infinite retry loops
}

async function request<T>(
  path: string,
  options: InternalRequestOptions = {}
): Promise<T> {
  const { timeout = DEFAULT_TIMEOUT, _retried = false, ...fetchOptions } = options;
  const method = (fetchOptions.method || 'GET').toUpperCase();
  
  // Try to refresh token if needed - await completion before proceeding
  let token = getToken();
  if (token && shouldRefreshToken(token)) {
    try {
      await tryRefreshToken();
      token = getToken(); // Get the refreshed token
    } catch {
      // Refresh failed, continue with old token
    }
  }
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...((fetchOptions.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // CSRF protection: add X-Requested-With header for non-GET requests
  if (method !== 'GET') {
    headers['X-Requested-With'] = 'XMLHttpRequest';
  }

  if (!(fetchOptions.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  // Set up AbortController for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const body = await res.json().catch(() => ({
        error: { code: ERROR_CODES.NETWORK_ERROR, message: "网络请求失败", detail: {} },
      }));

      if (res.status === 401) {
        // Don't clear auth for login endpoints — surface the real error
        const isLoginRequest = path.startsWith("/auth/token-login")
          || path.startsWith("/auth/admin-login");
        
        // If not a login request and haven't retried yet, try refreshing token
        if (!isLoginRequest && !_retried) {
          try {
            const newToken = await tryRefreshToken();
            if (newToken) {
              // Retry the request with the new token
              return request<T>(path, { ...options, _retried: true });
            }
          } catch {
            // Refresh failed, fall through to clear auth
          }
        }
        
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
  } catch (err) {
    clearTimeout(timeoutId);
    
    // Handle abort/timeout
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ApiError({
        code: ERROR_CODES.REQUEST_TIMEOUT,
        message: '请求超时，请检查网络后重试',
        detail: { timeout },
      });
    }
    
    throw err;
  }
}

export const api = {
  get: <T>(path: string, options?: { timeout?: number }) => 
    request<T>(path, options),
  post: <T>(path: string, body?: unknown, options?: { timeout?: number }) =>
    request<T>(path, {
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
      ...options,
    }),
  patch: <T>(path: string, body?: unknown, options?: { timeout?: number }) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body), ...options }),
  delete: <T>(path: string, options?: { timeout?: number }) => 
    request<T>(path, { method: "DELETE", ...options }),
};

export { ApiError };
