"use client";

import { useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  useAdminMetrics,
  useAdminHealth,
  useModelCalls,
  useSystemMode,
  useCostTrend,
  useFallbackStats,
  useErrorStats,
  useLatencyStats,
} from "@/lib/hooks";
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

const REASON_LABELS: Record<string, string> = {
  timeout: "超时",
  rate_limit: "限流",
  service_error: "服务错误",
  unknown: "未知",
  other: "其他",
};

export default function MetricsPage() {
  const [timeRange, setTimeRange] = useState("today");
  const { data: m, isLoading } = useAdminMetrics();
  const { data: health } = useAdminHealth() as { data: HealthStatus | undefined };
  const { data: modelCalls } = useModelCalls() as { data: ModelCallsData | undefined };
  const { data: modeData } = useSystemMode();
  const { data: cost } = useCostTrend(timeRange);
  const { data: fallback } = useFallbackStats(timeRange);
  const { data: errors } = useErrorStats(timeRange);
  const { data: latency } = useLatencyStats(timeRange);

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
          <>
            {/* Row 1: Activity + Health */}
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
                    {(["database", "redis", "celery"] as const).map((key) => (
                      <div key={key} className="flex items-center justify-between py-2">
                        <span className="text-sm text-text-secondary">{key === "database" ? "数据库" : key === "redis" ? "Redis" : "Celery"}</span>
                        <div className="flex items-center gap-2"><StatusDot status={health[key]} /><span className="text-sm">{health[key]}</span></div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>

            {/* Row 2: Model calls + System mode */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {modelCalls && (
                <Card>
                  <CardTitle>模型调用统计</CardTitle>
                  <MetricRow label="总调用次数" value={modelCalls.total} unit="次" />
                  {modelCalls.by_agent.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-text-tertiary mb-2">按 Agent</p>
                      <div className="space-y-1.5">
                        {modelCalls.by_agent.map((a) => (
                          <div key={a.agent || "unknown"} className="flex items-center justify-between text-xs">
                            <span className="text-text-secondary">{a.agent || "unknown"}</span>
                            <span className="font-medium">{a.count}次</span>
                          </div>
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

            {/* Row 3: Cost + Fallback */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {cost && (
                <Card>
                  <CardTitle>成本追踪</CardTitle>
                  <MetricRow label="累计成本" value={`¥${cost.total_cost}`} unit="" />
                  <MetricRow label="日均成本" value={`¥${cost.daily_avg_cost}`} unit="" />
                  {cost.by_model.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-text-tertiary mb-2">按模型</p>
                      <div className="space-y-1.5">
                        {cost.by_model.map((m) => (
                          <div key={m.model} className="flex items-center justify-between text-xs">
                            <span className="text-text-secondary">{m.model}</span>
                            <span className="font-medium">¥{m.cost.toFixed(2)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {cost.trend.length > 1 && (
                    <div className="mt-3">
                      <p className="text-xs text-text-tertiary mb-2">每日趋势</p>
                      <div className="space-y-1">
                        {cost.trend.map((t) => (
                          <div key={t.date} className="flex items-center justify-between text-xs">
                            <span className="text-text-tertiary">{t.date}</span>
                            <span>¥{t.cost.toFixed(2)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {fallback && (
                <Card>
                  <CardTitle>降级统计</CardTitle>
                  <MetricRow label="降级次数" value={fallback.fallback_count} unit="次" />
                  <MetricRow label="降级率" value={`${(fallback.fallback_rate * 100).toFixed(1)}%`} unit="" />
                  {fallback.by_reason.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-text-tertiary mb-2">降级原因</p>
                      <div className="flex gap-2 flex-wrap">
                        {fallback.by_reason.map((r) => (
                          <Badge key={r.reason}>{REASON_LABELS[r.reason] || r.reason}: {r.count}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              )}
            </div>

            {/* Row 4: Errors + Latency */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {errors && (
                <Card>
                  <CardTitle>错误统计</CardTitle>
                  <MetricRow label="错误总数" value={errors.total_errors} unit="个" />
                  {errors.by_type.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-text-tertiary mb-2">按类型</p>
                      <div className="space-y-1.5">
                        {errors.by_type.map((t) => (
                          <div key={t.type} className="flex items-center justify-between text-xs">
                            <span className="text-text-secondary">{t.type}</span>
                            <span className="font-medium">{t.count}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {errors.by_agent.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-text-tertiary mb-2">按 Agent</p>
                      <div className="space-y-1.5">
                        {errors.by_agent.map((a) => (
                          <div key={a.agent} className="flex items-center justify-between text-xs">
                            <span className="text-text-secondary">{a.agent}</span>
                            <span className="font-medium">{a.error_count}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {latency && (
                <Card>
                  <CardTitle>性能指标</CardTitle>
                  <MetricRow label="平均延迟" value={`${(latency.avg_latency_ms / 1000).toFixed(1)}s`} unit="" />
                  <MetricRow label="P95" value={`${(latency.p95_latency_ms / 1000).toFixed(1)}s`} unit="" />
                  <MetricRow label="P99" value={`${(latency.p99_latency_ms / 1000).toFixed(1)}s`} unit="" />
                  {latency.by_agent.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-text-tertiary mb-2">按 Agent</p>
                      <div className="space-y-1.5">
                        {latency.by_agent.map((a) => (
                          <div key={a.agent} className="flex items-center justify-between text-xs">
                            <span className="text-text-secondary">{a.agent}</span>
                            <span className="font-medium">avg {(a.avg_ms / 1000).toFixed(1)}s / P95 {(a.p95_ms / 1000).toFixed(1)}s</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              )}
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
