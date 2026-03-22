import { api, AUTH_STORAGE_KEYS } from "./api";
import type { AuthResponse, AuthUser } from "@/types/api";

// Cookie max-age in seconds (30 days, matching backend token expiry)
const TOKEN_COOKIE_MAX_AGE = 30 * 24 * 60 * 60;

export interface StoredAuth {
  token: string;
  role: "student" | "parent" | "admin";
  userName: string;
  studentId: number | null;
}

/**
 * Set access_token cookie.
 * Note: For XSS protection this should ideally be set via a server-side
 * API route with httpOnly flag. For now we set Secure + SameSite=Lax
 * to mitigate CSRF. Full httpOnly migration requires a server-side
 * login proxy route.
 */
export function setTokenCookie(token: string, maxAge: number = TOKEN_COOKIE_MAX_AGE): void {
  if (typeof document === "undefined") return;
  const secure = window.location.protocol === "https:" ? ";Secure" : "";
  document.cookie = `access_token=${token};path=/;max-age=${maxAge};SameSite=Lax${secure}`;
}

/**
 * Clear access_token cookie
 */
export function clearTokenCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = "access_token=;path=/;max-age=0;SameSite=Lax";
}

/**
 * Get token from cookie
 */
export function getTokenFromCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)access_token=([^;]*)/);
  return match ? match[1] : null;
}

/**
 * Migrate token from localStorage to cookie if needed.
 * Called on app initialization to ensure middleware can read the token.
 */
export function migrateTokenToCookie(): void {
  if (typeof window === "undefined") return;
  
  const cookieToken = getTokenFromCookie();
  const localToken = localStorage.getItem("access_token");
  
  // If cookie is missing but localStorage has token, sync to cookie
  if (!cookieToken && localToken) {
    setTokenCookie(localToken);
  }
}

export function getStoredAuth(): StoredAuth | null {
  if (typeof window === "undefined") return null;
  
  // Ensure token migration on access
  migrateTokenToCookie();
  
  const token = localStorage.getItem("access_token");
  if (!token) return null;
  return {
    token,
    role: (localStorage.getItem("user_role") as StoredAuth["role"]) || "student",
    userName: localStorage.getItem("user_name") || "",
    studentId: localStorage.getItem("student_id")
      ? parseInt(localStorage.getItem("student_id")!)
      : null,
  };
}

export function saveAuth(res: AuthResponse): void {
  // Clear all previous user state to prevent cross-account leakage
  // (e.g. stale onboarding_completed, onboarding_draft from a prior student)
  for (const key of AUTH_STORAGE_KEYS) localStorage.removeItem(key);

  localStorage.setItem("access_token", res.access_token);
  localStorage.setItem("user_role", res.user.role);
  localStorage.setItem("user_name", res.user.nickname);
  if (res.user.student_id) {
    localStorage.setItem("student_id", String(res.user.student_id));
  }
  
  // Also save token to cookie for middleware access
  setTokenCookie(res.access_token);
}

export function clearAuth(): void {
  // Clear localStorage
  for (const key of AUTH_STORAGE_KEYS) localStorage.removeItem(key);
  // Clear cookie
  clearTokenCookie();
}

export async function loginWithToken(
  token: string,
  role: "student" | "parent"
): Promise<AuthResponse> {
  return api.post<AuthResponse>("/auth/token-login", { token, role });
}

export async function loginAdmin(
  username: string,
  password: string
): Promise<AuthResponse> {
  return api.post<AuthResponse>("/auth/admin-login", { username, password });
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return api.get<AuthUser>("/auth/me");
}
