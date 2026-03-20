import { api, AUTH_STORAGE_KEYS } from "./api";
import type { AuthResponse, AuthUser } from "@/types/api";

export interface StoredAuth {
  token: string;
  role: "student" | "parent" | "admin";
  userName: string;
  studentId: number | null;
}

export function getStoredAuth(): StoredAuth | null {
  if (typeof window === "undefined") return null;
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
}

export function clearAuth(): void {
  for (const key of AUTH_STORAGE_KEYS) localStorage.removeItem(key);
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
