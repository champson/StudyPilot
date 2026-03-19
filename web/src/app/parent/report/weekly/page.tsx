"use client";

import { useState, useEffect } from "react";
import { PageHeader } from "@/components/layout/app-header";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageSkeleton } from "@/components/ui/skeleton";
import { cn, riskLevelLabels, formatMinutes } from "@/lib/utils";
import { mockWeeklyReport } from "@/lib/mock-data";

export default function ParentWeeklyReportPage() {
  const [loading, setLoading] = useState(true);
  const report = mockWeeklyReport;

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  if (loading) return <><PageHeader title="孩子学习周报" /><PageSkeleton /></>;

  const wow = report.week_over_week;

  return (
    <div className="min-h-screen bg-bg">
      <PageHeader title="孩子学习周报（家长视角）" rightContent={
        <select className="px-3 py-1.5 border border-border rounded-lg text-sm bg-card">
          <option>第12周 3.11-3.17</option>
          <option>第11周 3.4-3.10</option>
        </select>
      } />

      <main className="max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-6">
        {/* Summary for parents - trend focused */}
        <div className="bg-primary-light border border-primary/20 rounded-xl p-4 md:p-5 mb-6">
          <p className="text-sm text-primary font-medium mb-2">📋 本周总结</p>
          <p className="text-sm text-text-primary leading-relaxed">
            小明本周学习了 <strong>{report.usage_days}</strong> 天，累计 <strong>{formatMinutes(report.total_minutes)}</strong>，
            完成率 <strong>{report.task_completion_rate}%</strong>。
            {wow.usage_days_change > 0 ? `比上周多学了${wow.usage_days_change}天，` : ""}
            修复了 <strong>{report.fixed_errors}</strong> 道错题。整体学习状态{report.task_completion_rate >= 70 ? "良好" : "需要关注"}。
          </p>
        </div>

        {/* Core Metrics - simplified */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">学习天数</p>
            <p className="text-xl font-bold">{report.usage_days}/7天</p>
            <p className={cn("text-xs", wow.usage_days_change >= 0 ? "text-success" : "text-error")}>
              {wow.usage_days_change >= 0 ? "↑" : "↓"}{Math.abs(wow.usage_days_change)}
            </p>
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">总时长</p>
            <p className="text-xl font-bold">{formatMinutes(report.total_minutes)}</p>
            <p className={cn("text-xs", wow.total_minutes_change >= 0 ? "text-success" : "text-error")}>
              {wow.total_minutes_change >= 0 ? "↑" : "↓"}{Math.abs(wow.total_minutes_change)}min
            </p>
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">完成率</p>
            <p className="text-xl font-bold">{report.task_completion_rate}%</p>
            <p className={cn("text-xs", wow.completion_rate_change >= 0 ? "text-success" : "text-error")}>
              {wow.completion_rate_change >= 0 ? "↑" : "↓"}{Math.abs(wow.completion_rate_change)}%
            </p>
          </Card>
        </div>

        {/* Subject Risk Summary - parents see risk trends, not details */}
        <Card className="mb-4">
          <CardTitle>各学科风险概览</CardTitle>
          <p className="text-xs text-text-tertiary mb-3">以下是各学科的整体状态，具体薄弱知识点已由系统自动安排复习</p>
          <div className="space-y-3">
            {report.subject_performances.map((sp) => {
              const risk = riskLevelLabels[sp.risk_level];
              return (
                <div key={sp.subject} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-sm">{sp.subject}</span>
                    <Badge className={risk ? `${risk.color} bg-transparent` : ""}>{risk?.label}</Badge>
                  </div>
                  <p className="text-xs text-text-secondary max-w-[50%] text-right">{sp.summary}</p>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Suggestions */}
        <Card className="mb-4">
          <CardTitle>关注建议</CardTitle>
          <ul className="space-y-2">
            {report.suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-text-primary">
                <span className="text-primary">•</span>
                {s}
              </li>
            ))}
          </ul>
        </Card>

        {/* Note about data masking */}
        <div className="text-center py-4">
          <p className="text-xs text-text-tertiary">
            家长视角仅展示趋势和风险概览，不包含具体题目、排名等敏感信息
          </p>
        </div>
      </main>
    </div>
  );
}
