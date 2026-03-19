"use client";

import { useState, useEffect } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton } from "@/components/ui/skeleton";
import { mockMetrics, mockCorrections } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

export default function AdminDashboardPage() {
  const [loading, setLoading] = useState(true);
  const metrics = mockMetrics;

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  const statCards = [
    { label: "活跃学生", value: metrics.active_students, icon: "👤", color: "text-primary" },
    { label: "今日计划", value: metrics.total_plans_today, icon: "📅", color: "text-success" },
    { label: "今日答疑", value: metrics.total_qa_sessions_today, icon: "💬", color: "text-warning" },
    { label: "今日上传", value: metrics.total_uploads_today, icon: "📤", color: "text-primary" },
  ];

  return (
    <AdminLayout>
      <div className="p-4 md:p-6 space-y-4">
        <h2 className="text-xl font-bold">管理仪表盘</h2>

        {loading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3"><CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>
        ) : (
          <>
            {/* Quick Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {statCards.map((s) => (
                <Card key={s.label} className="text-center">
                  <p className="text-2xl mb-1">{s.icon}</p>
                  <p className={cn("text-2xl font-bold", s.color)}>{s.value}</p>
                  <p className="text-xs text-text-tertiary">{s.label}</p>
                </Card>
              ))}
            </div>

            {/* System Health */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardTitle>系统健康</CardTitle>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">LLM 调用次数</span>
                    <span className="text-sm font-medium">{metrics.llm_calls_today}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">LLM 费用（今日）</span>
                    <span className="text-sm font-medium">¥{metrics.llm_cost_today.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">平均响应时间</span>
                    <span className="text-sm font-medium">{metrics.avg_response_time_ms}ms</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">错误率</span>
                    <span className={cn("text-sm font-medium", metrics.error_rate > 5 ? "text-error" : "text-success")}>{metrics.error_rate}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">OCR 成功率</span>
                    <span className="text-sm font-medium text-success">{metrics.ocr_success_rate}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">降级率</span>
                    <span className={cn("text-sm font-medium", metrics.fallback_rate > 10 ? "text-warning" : "text-success")}>{metrics.fallback_rate}%</span>
                  </div>
                </div>
              </Card>

              <Card>
                <CardTitle>待处理纠偏</CardTitle>
                <div className="space-y-2">
                  {mockCorrections.filter((c) => c.status === "pending").slice(0, 5).map((c) => (
                    <div key={c.id} className="p-2.5 bg-gray-50 rounded-lg">
                      <div className="flex items-center justify-between mb-1">
                        <Badge variant={c.type === "ocr" ? "warning" : c.type === "knowledge" ? "error" : "default"}>
                          {c.type.toUpperCase()}
                        </Badge>
                        <span className="text-xs text-text-tertiary">{c.student_name}</span>
                      </div>
                      <p className="text-xs text-text-secondary line-clamp-2">{c.description}</p>
                    </div>
                  ))}
                  {mockCorrections.filter((c) => c.status === "pending").length === 0 && (
                    <p className="text-sm text-text-tertiary text-center py-4">暂无待处理纠偏</p>
                  )}
                </div>
              </Card>
            </div>

            {/* Mode Toggle */}
            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="mb-1">系统运行模式</CardTitle>
                  <p className="text-sm text-text-secondary">当前模式影响所有 Agent 的模型选择</p>
                </div>
                <div className="flex bg-gray-100 rounded-lg p-1">
                  <button className="px-4 py-2 text-sm bg-card rounded-md shadow-sm font-medium text-primary">正常效果</button>
                  <button className="px-4 py-2 text-sm text-text-secondary rounded-md">最优效果</button>
                </div>
              </div>
            </Card>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
