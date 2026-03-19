"use client";

import { useState, useEffect } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { mockMetrics } from "@/lib/mock-data";

export default function MetricsPage() {
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("today");
  const m = mockMetrics;

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 500);
    return () => clearTimeout(timer);
  }, []);

  // Metric card helper
  function MetricRow({ label, value, unit, threshold, thresholdType = "below" }: {
    label: string; value: number; unit: string; threshold?: number; thresholdType?: "above" | "below";
  }) {
    const isAlert = threshold !== undefined && (thresholdType === "above" ? value > threshold : value < threshold);
    return (
      <div className="flex items-center justify-between py-2.5 border-b border-border-light last:border-0">
        <span className="text-sm text-text-secondary">{label}</span>
        <span className={cn("text-sm font-medium", isAlert ? "text-error" : "text-text-primary")}>
          {typeof value === "number" && value % 1 !== 0 ? value.toFixed(1) : value}{unit}
          {isAlert && <span className="ml-1 text-error text-xs">⚠</span>}
        </span>
      </div>
    );
  }

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

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4"><CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>
        ) : (
          <>
            {/* Usage Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardTitle>📊 用户活跃度</CardTitle>
                <MetricRow label="活跃学生数" value={m.active_students} unit="人" />
                <MetricRow label="今日生成计划" value={m.total_plans_today} unit="个" />
                <MetricRow label="今日答疑会话" value={m.total_qa_sessions_today} unit="次" />
                <MetricRow label="今日上传量" value={m.total_uploads_today} unit="次" />
              </Card>

              <Card>
                <CardTitle>🤖 LLM 调用统计</CardTitle>
                <MetricRow label="总调用次数" value={m.llm_calls_today} unit="次" />
                <MetricRow label="总费用" value={m.llm_cost_today} unit="元" />
                <MetricRow label="平均响应时间" value={m.avg_response_time_ms} unit="ms" threshold={3000} thresholdType="above" />
                <MetricRow label="错误率" value={m.error_rate} unit="%" threshold={5} thresholdType="above" />
              </Card>

              <Card>
                <CardTitle>📸 OCR 处理统计</CardTitle>
                <MetricRow label="OCR 成功率" value={m.ocr_success_rate} unit="%" threshold={90} thresholdType="below" />
                <MetricRow label="降级率" value={m.fallback_rate} unit="%" threshold={15} thresholdType="above" />
              </Card>

              <Card>
                <CardTitle>💰 成本分析</CardTitle>
                <div className="space-y-3">
                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm text-text-secondary">当前模式</span>
                    <Badge variant="primary">正常效果模式</Badge>
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm text-text-secondary">今日 LLM 费用</span>
                    <span className="text-sm font-medium">¥{m.llm_cost_today.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm text-text-secondary">预估月度费用</span>
                    <span className="text-sm font-medium">¥{(m.llm_cost_today * 30).toFixed(0)}</span>
                  </div>

                  {/* Cost bar visualization */}
                  <div className="mt-2">
                    <div className="flex items-center justify-between text-xs text-text-tertiary mb-1">
                      <span>月度预算使用</span>
                      <span>¥{(m.llm_cost_today * 30).toFixed(0)} / ¥1,200</span>
                    </div>
                    <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all",
                          (m.llm_cost_today * 30) / 1200 > 0.8 ? "bg-error" : (m.llm_cost_today * 30) / 1200 > 0.6 ? "bg-warning" : "bg-success"
                        )}
                        style={{ width: `${Math.min(100, ((m.llm_cost_today * 30) / 1200) * 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            {/* Alert History */}
            <Card>
              <CardTitle>🔔 近期告警</CardTitle>
              <div className="space-y-2">
                <div className="flex items-center gap-3 p-3 bg-warning-light rounded-lg">
                  <Badge variant="warning">WARN</Badge>
                  <div className="flex-1">
                    <p className="text-sm">OCR 成功率下降至 89%，低于 90% 阈值</p>
                    <p className="text-xs text-text-tertiary mt-0.5">今天 10:30</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <Badge>INFO</Badge>
                  <div className="flex-1">
                    <p className="text-sm">系统模式已切换为正常效果模式</p>
                    <p className="text-xs text-text-tertiary mt-0.5">今天 08:00</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <Badge>INFO</Badge>
                  <div className="flex-1">
                    <p className="text-sm">每日数据库备份完成</p>
                    <p className="text-xs text-text-tertiary mt-0.5">今天 03:00</p>
                  </div>
                </div>
              </div>
            </Card>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
