"use client";

import { useState, useEffect } from "react";
import { PageHeader } from "@/components/layout/app-header";
import { Card, CardTitle, CardDivider } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { cn, riskLevelLabels, formatMinutes } from "@/lib/utils";
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

  const wow = report.week_over_week;

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
            <p className={cn("text-xs mt-1", wow.usage_days_change >= 0 ? "text-success" : "text-error")}>
              {wow.usage_days_change >= 0 ? "↑" : "↓"} 比上周{wow.usage_days_change >= 0 ? "+" : ""}{wow.usage_days_change}
            </p>
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary mb-1">⏱️ 总时长</p>
            <p className="text-2xl font-bold text-text-primary">{formatMinutes(report.total_minutes)}</p>
            <p className={cn("text-xs mt-1", wow.total_minutes_change >= 0 ? "text-success" : "text-error")}>
              {wow.total_minutes_change >= 0 ? "↑" : "↓"} 比上周{wow.total_minutes_change >= 0 ? "+" : ""}{wow.total_minutes_change}min
            </p>
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary mb-1">✅ 完成率</p>
            <p className="text-2xl font-bold text-text-primary">{report.task_completion_rate}%</p>
            <p className={cn("text-xs mt-1", wow.completion_rate_change >= 0 ? "text-success" : "text-error")}>
              {wow.completion_rate_change >= 0 ? "↑" : "↓"} 比上周{wow.completion_rate_change >= 0 ? "+" : ""}{wow.completion_rate_change}%
            </p>
          </Card>
        </div>

        {/* Subject Performance */}
        <Card className="mb-4">
          <CardTitle>学科表现变化</CardTitle>
          <div className="space-y-4">
            {report.subject_performances.map((sp) => {
              const risk = riskLevelLabels[sp.risk_level];
              return (
                <div key={sp.subject} className="p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-sm">{sp.subject}</span>
                    <Badge className={risk ? `${risk.color} bg-transparent` : ""}>{risk?.label}</Badge>
                  </div>
                  <p className="text-sm text-text-secondary mb-2">{sp.summary}</p>
                  {sp.knowledge_points_improved.length > 0 && (
                    <p className="text-xs text-success">↑ 提升：{sp.knowledge_points_improved.join("、")}</p>
                  )}
                  {sp.knowledge_points_declined.length > 0 && (
                    <p className="text-xs text-error mt-0.5">↓ 下降：{sp.knowledge_points_declined.join("、")}</p>
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        {/* Risk Points */}
        <Card className="mb-4">
          <CardTitle>薄弱点与高风险知识点</CardTitle>
          <div className="mb-4">
            <p className="text-xs text-text-tertiary mb-2">高风险知识点</p>
            <div className="flex gap-2 flex-wrap">
              {report.high_risk_points.map((p) => (
                <Badge key={p} variant="error">{p}</Badge>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs text-text-tertiary mb-2">反复错误点</p>
            <div className="flex gap-2 flex-wrap">
              {report.repeated_errors.map((e) => (
                <Badge key={e} variant="warning">{e}</Badge>
              ))}
            </div>
          </div>
        </Card>

        {/* Suggestions */}
        <Card>
          <CardTitle>下阶段建议</CardTitle>
          <ul className="space-y-3">
            {report.suggestions.map((s, i) => (
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
