"use client";

import { useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useAdminMetrics, useAdminHealth, useModelCalls, useSystemMode } from "@/lib/hooks";
import type { HealthStatus, ModelCallsData } from "@/types/api";

function MetricRow({ label, value, unit }: { label: string; value: number | string; unit: string }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border-light last:border-0">
      <span className="text-sm text-text-secondary">{label}</span>
      <span className="text-sm font-medium text-text-primary">{value}{unit}</span>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const color = status === "ok" ? "bg-success" : status === "degraded" ? "bg-warning" : "bg-error";
  return <span className={cn("inline-block w-2 h-2 rounded-full", color)} />;
}

export default function MetricsPage() {
  const [timeRange, setTimeRange] = useState("today");
  const { data: m, isLoading } = useAdminMetrics();
  const { data: health } = useAdminHealth() as { data: HealthStatus | undefined };
  const { data: modelCalls } = useModelCalls() as { data: ModelCallsData | undefined };
  const { data: modeData } = useSystemMode();

  const currentMode = modeData?.mode || "normal";

  return (
    <AdminLayout>
      <div className="p-4 md:p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">监控统计</h2>
          <div className="flex bg-gray-100 rounded-lg p-1">
            {[
              { value: "today", label: "今日" },
              { value: "week", label: "本周" },
              { value: "month", label: "本月" },
            ].map((t) => (
              <button
                key={t.value}
                onClick={() => setTimeRange(t.value)}
                className={cn(
                  "px-3 py-1.5 text-sm rounded-md transition-colors",
                  timeRange === t.value ? "bg-card shadow-sm font-medium text-primary" : "text-text-secondary"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {isLoading || !m ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4"><CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardTitle>用户活跃度</CardTitle>
              <MetricRow label="活跃学生数" value={m.active_students} unit="人" />
              <MetricRow label="今日生成计划" value={m.plans_generated} unit="个" />
              <MetricRow label="今日答疑会话" value={m.qa_sessions} unit="次" />
              <MetricRow label="今日上传量" value={m.uploads} unit="次" />
            </Card>

            {health && (
              <Card>
                <CardTitle>系统健康</CardTitle>
                <div className="space-y-3">
                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm text-text-secondary">数据库</span>
                    <div className="flex items-center gap-2"><StatusDot status={health.database} /><span className="text-sm">{health.database}</span></div>
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm text-text-secondary">Redis</span>
                    <div className="flex items-center gap-2"><StatusDot status={health.redis} /><span className="text-sm">{health.redis}</span></div>
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm text-text-secondary">Celery</span>
                    <div className="flex items-center gap-2"><StatusDot status={health.celery} /><span className="text-sm">{health.celery}</span></div>
                  </div>
                </div>
              </Card>
            )}

            {modelCalls && (
              <Card>
                <CardTitle>模型调用统计</CardTitle>
                <MetricRow label="总调用次数" value={modelCalls.total} unit="次" />
                {modelCalls.by_provider.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs text-text-tertiary mb-2">按提供商</p>
                    <div className="flex gap-2 flex-wrap">
                      {modelCalls.by_provider.map((p) => (
                        <Badge key={p.provider || "unknown"}>{p.provider || "unknown"}: {p.count}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            )}

            <Card>
              <CardTitle>系统模式</CardTitle>
              <div className="flex items-center justify-between py-2">
                <span className="text-sm text-text-secondary">当前模式</span>
                <Badge variant="primary">{currentMode === "best" ? "最优效果模式" : "正常效果模式"}</Badge>
              </div>
            </Card>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
