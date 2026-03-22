"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/app-header";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { EmptyState } from "@/components/ui/empty-state";
import { riskLevelLabels, trendLabels, formatMinutes } from "@/lib/utils";
import { useWeeklyReport } from "@/lib/hooks";
import { api, ApiError, ERROR_CODES } from "@/lib/api";
import { WeekSelector, useRecentWeeks } from "@/components/report/week-selector";

function ComparisonTag({ current, previous, unit, invert }: { current: number; previous?: number | null; unit: string; invert?: boolean }) {
  if (previous == null) return null;
  const diff = current - previous;
  if (diff === 0) return <span className="text-xs text-text-tertiary">→ 与上周持平</span>;
  const isPositive = invert ? diff < 0 : diff > 0;
  const arrow = diff > 0 ? "↑" : "↓";
  const color = isPositive ? "text-success" : "text-error";
  const absVal = Math.abs(diff);
  return <span className={`text-xs ${color}`}>{arrow} 比上周{diff > 0 ? "+" : ""}{unit === "%" ? `${Math.round(absVal * 100)}%` : `${absVal}${unit}`}</span>;
}

export default function WeeklyReportPage() {
  const weeks = useRecentWeeks();
  const [selectedWeek, setSelectedWeek] = useState(() => weeks[0]?.value);
  const { toast } = useToast();
  const currentWeek = weeks[0]?.value;
  const fallbackWeek = weeks[1]?.value ?? null;
  const {
    data: primaryReport,
    error: primaryError,
    isLoading: primaryLoading,
  } = useWeeklyReport(selectedWeek);
  const shouldFallback =
    selectedWeek === currentWeek &&
    fallbackWeek !== null &&
    primaryError instanceof ApiError &&
    primaryError.code === ERROR_CODES.REPORT_NOT_FOUND;
  const {
    data: fallbackReport,
    isLoading: fallbackLoading,
  } = useWeeklyReport(shouldFallback ? fallbackWeek : null);
  const report = primaryReport ?? fallbackReport;
  const isLoading = primaryLoading || (shouldFallback && fallbackLoading);
  const displayedWeek = primaryReport ? selectedWeek : fallbackReport ? fallbackWeek : selectedWeek;

  async function handleShare() {
    if (!report) return;
    try {
      const result = await api.post<{ share_url: string; expires_at: string; share_token?: string }>(
        `/student/report/share?week=${encodeURIComponent(report.report_week)}`
      );
      const shareUrl = result.share_token
        ? `${window.location.origin}/share/${result.share_token}`
        : `${window.location.origin}${result.share_url}`;
      await navigator.clipboard.writeText(shareUrl);
      toast("分享链接已复制到剪贴板", "success");
    } catch {
      toast("生成分享链接失败", "error");
    }
  }

  if (isLoading) return <><PageHeader title="本周学习报告" backHref="/dashboard" /><PageSkeleton /></>;
  if (!report) return <><PageHeader title="本周学习报告" backHref="/dashboard" /><div className="max-w-4xl mx-auto px-4 py-12"><EmptyState icon="📊" title="暂无周报数据" description="完成一周学习后将自动生成" /></div></>;

  return (
    <div className="min-h-screen bg-bg">
      <PageHeader
        title="本周学习报告"
        backHref="/dashboard"
        rightContent={
          <div className="flex items-center gap-2">
            <WeekSelector value={displayedWeek} onChange={setSelectedWeek} />
            <Button variant="outline" size="sm" onClick={handleShare}>分享</Button>
          </div>
        }
      />

      <main className="max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-6">
        {/* Core Metrics with comparison */}
        <div className="grid grid-cols-3 gap-3 md:gap-4 mb-6">
          <Card className="text-center">
            <p className="text-xs text-text-tertiary mb-1">学习天数</p>
            <p className="text-2xl font-bold text-text-primary">{report.usage_days} / 7 <span className="text-sm font-normal">天</span></p>
            <ComparisonTag current={report.usage_days ?? 0} previous={report.previous_usage_days} unit="天" />
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary mb-1">总时长</p>
            <p className="text-2xl font-bold text-text-primary">{formatMinutes(report.total_minutes ?? 0)}</p>
            <ComparisonTag current={report.total_minutes ?? 0} previous={report.previous_total_minutes} unit="min" />
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary mb-1">完成率</p>
            <p className="text-2xl font-bold text-text-primary">{Math.round((report.task_completion_rate ?? 0) * 100)}%</p>
            <ComparisonTag current={report.task_completion_rate ?? 0} previous={report.previous_task_completion_rate} unit="%" />
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
        {report.high_risk_knowledge_points.length > 0 && (
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
        )}

        {/* Suggestions */}
        {report.next_stage_suggestions.length > 0 && (
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
        )}
      </main>
    </div>
  );
}
