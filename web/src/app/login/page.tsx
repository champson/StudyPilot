"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { loginWithToken, loginAdmin, saveAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import type { AuthResponse } from "@/types/api";

function LoginPageContent() {
  const [role, setRole] = useState<"student" | "parent" | "admin">("student");
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect");
  const { toast } = useToast();

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();

    if (role === "admin") {
      if (!username || !password) {
        toast("请填写用户名和密码", "error");
        return;
      }
    } else {
      if (!token) {
        toast("请输入登录令牌", "error");
        return;
      }
    }

    setLoading(true);

    try {
      if (role === "admin") {
        const res = await loginAdmin(username, password);
        saveAuth(res);
        router.push(redirectTo?.startsWith("/admin") ? redirectTo : "/admin/dashboard");
      } else {
        const res = await loginWithToken(token, role);
        saveAuth(res);
        if (role === "student") {
          if (!res.user.student_id) {
            // First-time student: create profile, then refresh token to get student_id in JWT
            try {
              await api.post("/student/profile", { grade: "高一" });
            } catch {
              // Profile may already exist from a prior partial flow — continue
            }
            // Refresh token so JWT now contains the newly created student_id.
            // Without this, all /student/* endpoints will 403 (student_id=null in JWT).
            const refreshed = await api.post<AuthResponse>("/auth/refresh");
            saveAuth(refreshed);
            router.push("/onboarding");
          } else {
            // Existing student: check onboarding status
            try {
              const status = await api.get<{ onboarding_completed: boolean }>("/student/onboarding/status");
              if (!status.onboarding_completed) {
                router.push("/onboarding");
              } else {
                localStorage.setItem("onboarding_completed", "true");
                router.push(redirectTo || "/dashboard");
              }
            } catch {
              router.push("/onboarding");
            }
          }
        } else {
          router.push(redirectTo?.startsWith("/parent") ? redirectTo : "/parent/report/weekly");
        }
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "INVALID_TOKEN") {
          toast("登录令牌无效，请联系管理员", "error");
        } else if (err.code === "INVALID_CREDENTIALS") {
          toast("用户名或密码错误", "error");
        } else {
          toast(err.message || "登录失败，请重试", "error");
        }
      } else {
        toast("网络错误，请检查连接", "error");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-primary rounded-2xl flex items-center justify-center text-white font-bold text-2xl mx-auto mb-4">AI</div>
          <h1 className="text-2xl font-bold text-text-primary">AI 伴学教练</h1>
          <p className="text-sm text-text-secondary mt-2">面向上海高中生的个性化学习助手</p>
        </div>

        <Card>
          <div className="flex bg-gray-100 rounded-lg p-1 mb-6">
            {(["student", "parent", "admin"] as const).map((r) => (
              <button
                key={r}
                onClick={() => setRole(r)}
                className={`flex-1 py-2 text-sm rounded-md transition-colors ${
                  role === r ? "bg-card text-primary font-medium shadow-sm" : "text-text-secondary"
                }`}
              >
                {r === "student" ? "学生" : r === "parent" ? "家长" : "管理员"}
              </button>
            ))}
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            {role === "admin" ? (
              <>
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-1.5">用户名</label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="请输入管理员用户名"
                    className="w-full px-3 py-2.5 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-1.5">密码</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="请输入密码"
                    className="w-full px-3 py-2.5 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                  />
                </div>
              </>
            ) : (
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1.5">
                  {role === "student" ? "学生令牌" : "家长令牌"}
                </label>
                <input
                  type="text"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder={`请输入${role === "student" ? "学生" : "家长"}登录令牌`}
                  className="w-full px-3 py-2.5 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                />
                <p className="text-xs text-text-tertiary mt-1.5">令牌由管理员分配，请联系管理员获取</p>
              </div>
            )}

            <Button type="submit" fullWidth size="lg" loading={loading}>
              登录
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-bg" />}>
      <LoginPageContent />
    </Suspense>
  );
}
