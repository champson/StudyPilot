"use client";

import { useState, useEffect } from "react";
import { PageHeader } from "@/components/layout/app-header";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { riskLevelLabels, trendLabels, formatMinutes } from "@/lib/utils";
import { mockWeeklyReport } from "@/lib/mock-data";

export default function WeeklyReportPage() {
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const report = mockWeeklyReport;

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  function handleShare() {
    toast("分享链接已生成并复制到剪贴板", "success");
  }

  if (loading) return <><PageHeader title="本周学习报告" backHref="/dashboard" /><PageSkeleton /></>;

  return (
    <div className="min-h-screen bg-bg">
      <PageHeader
        title="本周学习报告"
        backHref="/dashboard"
        rightContent={
          <div className="flex items-center gap-2">
            <select className="px-3 py-1.5 border border-border rounded-lg text-sm bg-card">
              <option>第12周 3.11-3.17</option>
              <option>第11周 3.4-3.10</option>
            </select>
            <Button variant="outline" size="sm" onClick={handleShare}>分享</Button>
          </div>
        }
      />

      <main className="max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-6">
        {/* Core Metrics */}
        <div className="grid grid-cols-3 gap-3 md:gap-4 mb-6">
          <Card className="text-center">
            <p className="text-xs text-text-tertiary mb-1">📅 学习天数</p>
            <p className="text-2xl font-bold text-text-primary">{report.usage_days} / 7 <span className="text-sm font-normal">天</span></p>
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary mb-1">⏱️ 总时长</p>
            <p className="text-2xl font-bold text-text-primary">{formatMinutes(report.total_minutes ?? 0)}</p>
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary mb-1">✅ 完成率</p>
            <p className="text-2xl font-bold text-text-primary">{report.task_completion_rate}%</p>
          </Card>
        </div>

        {/* Subject Trends */}
        <Card className="mb-4">
          <CardTitle>学科趋势</CardTitle>
          <div className="space-y-4">
            {report.subject_trends.map((st) => {
              const risk = riskLevelLabels[st.risk_level];
              const trend = trendLabels[st.trend];
              return (
                <div key={st.subject_name} className="p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{st.subject_name}</span>
                      <Badge className={risk ? `${risk.color} bg-transparent` : ""}>{risk?.label}</Badge>
                    </div>
                    {trend && (
                      <span className={`text-sm ${st.trend === "improving" ? "text-success" : st.trend === "declining" ? "text-error" : "text-text-tertiary"}`}>
                        {trend.icon} {trend.label}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Risk Points */}
        <Card className="mb-4">
          <CardTitle>高风险知识点</CardTitle>
          <div className="space-y-3 mb-4">
            {report.high_risk_knowledge_points.map((p) => (
              <div key={p.name} className="flex items-center justify-between p-2 bg-error-light/30 rounded-lg">
                <div>
                  <span className="text-sm font-medium">{p.name}</span>
                  <span className="text-xs text-text-tertiary ml-2">{p.subject_name}</span>
                </div>
                <Badge variant="error">{p.status}</Badge>
              </div>
            ))}
          </div>
          {report.repeated_error_points.length > 0 && (
            <>
              <p className="text-xs text-text-tertiary mb-2">反复错误点</p>
              <div className="flex gap-2 flex-wrap">
                {report.repeated_error_points.map((e) => (
                  <Badge key={e.name} variant="warning">{e.name} ({e.error_count}次)</Badge>
                ))}
              </div>
            </>
          )}
        </Card>

        {/* Suggestions */}
        <Card>
          <CardTitle>下阶段建议</CardTitle>
          <ul className="space-y-3">
            {report.next_stage_suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-3">
                <span className="w-6 h-6 bg-primary-light text-primary rounded-full flex items-center justify-center text-xs font-medium shrink-0">{i + 1}</span>
                <p className="text-sm text-text-primary leading-relaxed">{s}</p>
              </li>
            ))}
          </ul>
        </Card>
      </main>
    </div>
  );
}
