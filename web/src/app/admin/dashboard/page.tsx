"use client";

import { useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { useAdminMetrics, usePendingCorrections, useSystemMode } from "@/lib/hooks";
import { api } from "@/lib/api";
import type { CorrectionItem } from "@/types/api";

export default function AdminDashboardPage() {
  const { toast } = useToast();
  const { data: metrics, isLoading } = useAdminMetrics();
  const { data: correctionsData } = usePendingCorrections(1);
  const { data: modeData, mutate: mutateMode } = useSystemMode();
  const [switching, setSwitching] = useState(false);

  const corrections: CorrectionItem[] = correctionsData?.items || [];
  const currentMode = modeData?.mode || "normal";

  async function switchMode(mode: string) {
    setSwitching(true);
    try {
      await api.post("/admin/system/mode", { mode });
      mutateMode();
      toast(`已切换到${mode === "best" ? "最优" : "正常"}效果模式`, "success");
    } catch {
      toast("切换失败", "error");
    } finally {
      setSwitching(false);
    }
  }

  const statCards = metrics ? [
    { label: "活跃学生", value: metrics.active_students, color: "text-primary" },
    { label: "今日计划", value: metrics.plans_generated, color: "text-success" },
    { label: "今日答疑", value: metrics.qa_sessions, color: "text-warning" },
    { label: "今日上传", value: metrics.uploads, color: "text-primary" },
  ] : [];

  return (
    <AdminLayout>
      <div className="p-4 md:p-6 space-y-4">
        <h2 className="text-xl font-bold">管理仪表盘</h2>

        {isLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3"><CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>
        ) : metrics ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {statCards.map((s) => (
                <Card key={s.label} className="text-center">
                  <p className={cn("text-2xl font-bold", s.color)}>{s.value}</p>
                  <p className="text-xs text-text-tertiary">{s.label}</p>
                </Card>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardTitle>待处理纠偏</CardTitle>
                <div className="space-y-2">
                  {corrections.slice(0, 5).map((c) => (
                    <div key={c.id} className="p-2.5 bg-gray-50 rounded-lg">
                      <div className="flex items-center justify-between mb-1">
                        <Badge variant={c.target_type === "ocr" ? "warning" : c.target_type === "knowledge" ? "error" : "default"}>
                          {c.target_type.toUpperCase()}
                        </Badge>
                        <span className="text-xs text-text-tertiary">{c.correction_reason}</span>
                      </div>
                      <p className="text-xs text-text-secondary line-clamp-2">目标 #{c.target_id}</p>
                    </div>
                  ))}
                  {corrections.length === 0 && (
                    <p className="text-sm text-text-tertiary text-center py-4">暂无待处理纠偏</p>
                  )}
                </div>
              </Card>

              <Card>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="mb-1">系统运行模式</CardTitle>
                    <p className="text-sm text-text-secondary">当前模式影响所有 Agent 的模型选择</p>
                  </div>
                  <div className="flex bg-gray-100 rounded-lg p-1">
                    <button
                      onClick={() => switchMode("normal")}
                      disabled={switching}
                      className={cn("px-4 py-2 text-sm rounded-md", currentMode === "normal" ? "bg-card shadow-sm font-medium text-primary" : "text-text-secondary")}
                    >
                      正常效果
                    </button>
                    <button
                      onClick={() => switchMode("best")}
                      disabled={switching}
                      className={cn("px-4 py-2 text-sm rounded-md", currentMode === "best" ? "bg-card shadow-sm font-medium text-primary" : "text-text-secondary")}
                    >
                      最优效果
                    </button>
                  </div>
                </div>
              </Card>
            </div>
          </>
        ) : (
          <p className="text-text-tertiary">无法加载数据</p>
        )}
      </div>
    </AdminLayout>
  );
}
