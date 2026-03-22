"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/app-header";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { riskLevelLabels, formatMinutes } from "@/lib/utils";
import { useParentWeeklyReport } from "@/lib/hooks";
import { ApiError, ERROR_CODES } from "@/lib/api";
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

export default function ParentWeeklyReportPage() {
  const weeks = useRecentWeeks();
  const [selectedWeek, setSelectedWeek] = useState(() => weeks[0]?.value);
  const currentWeek = weeks[0]?.value;
  const fallbackWeek = weeks[1]?.value ?? null;
  const {
    data: primaryReport,
    error: primaryError,
    isLoading: primaryLoading,
  } = useParentWeeklyReport(selectedWeek);
  const shouldFallback =
    selectedWeek === currentWeek &&
    fallbackWeek !== null &&
    primaryError instanceof ApiError &&
    primaryError.code === ERROR_CODES.REPORT_NOT_FOUND;
  const {
    data: fallbackReport,
    isLoading: fallbackLoading,
  } = useParentWeeklyReport(shouldFallback ? fallbackWeek : null);
  const report = primaryReport ?? fallbackReport;
  const isLoading = primaryLoading || (shouldFallback && fallbackLoading);
  const displayedWeek = primaryReport ? selectedWeek : fallbackReport ? fallbackWeek : selectedWeek;

  if (isLoading) return <><PageHeader title="孩子学习周报" /><PageSkeleton /></>;
  if (!report) return <><PageHeader title="孩子学习周报" /><div className="max-w-4xl mx-auto px-4 py-12"><EmptyState icon="📊" title="暂无周报数据" description="孩子完成一周学习后将自动生成" /></div></>;

  return (
    <div className="min-h-screen bg-bg">
      <PageHeader title="孩子学习周报（家长视角）" rightContent={
        <WeekSelector value={displayedWeek} onChange={setSelectedWeek} />
      } />

      <main className="max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-6">
        {report.trend_description && (
          <div className="bg-primary-light border border-primary/20 rounded-xl p-4 md:p-5 mb-6">
            <p className="text-sm text-primary font-medium mb-2">本周总结</p>
            <p className="text-sm text-text-primary leading-relaxed">{report.trend_description}</p>
          </div>
        )}

        <div className="grid grid-cols-3 gap-3 mb-6">
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">学习天数</p>
            <p className="text-xl font-bold">{report.usage_days}/7天</p>
            <ComparisonTag current={report.usage_days ?? 0} previous={report.previous_usage_days} unit="天" />
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">总时长</p>
            <p className="text-xl font-bold">{formatMinutes(report.total_minutes ?? 0)}</p>
            <ComparisonTag current={report.total_minutes ?? 0} previous={report.previous_total_minutes} unit="min" />
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">完成率</p>
            <p className="text-xl font-bold">{Math.round((report.task_completion_rate ?? 0) * 100)}%</p>
            <ComparisonTag current={report.task_completion_rate ?? 0} previous={report.previous_task_completion_rate} unit="%" />
          </Card>
        </div>

        {report.avg_daily_minutes != null && (
          <Card className="mb-4 text-center">
            <p className="text-xs text-text-tertiary">日均学习时长</p>
            <p className="text-xl font-bold">{formatMinutes(report.avg_daily_minutes)}</p>
          </Card>
        )}

        {/* Risk Summary */}
        {report.risk_summary && (report.risk_summary.high_risk_points.length > 0 || report.risk_summary.repeated_errors.length > 0) && (
          <Card className="mb-4">
            <CardTitle>风险与关注点</CardTitle>
            {report.risk_summary.high_risk_points.length > 0 && (
              <div className="mb-3">
                <p className="text-xs text-text-tertiary mb-2">高风险知识点</p>
                <div className="space-y-2">
                  {report.risk_summary.high_risk_points.map((p) => (
                    <div key={p.name} className="flex items-center justify-between p-2 bg-error-light/30 rounded-lg">
                      <span className="text-sm">{p.name}</span>
                      <span className="text-xs text-text-tertiary">{p.subject_name}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {report.risk_summary.repeated_errors.length > 0 && (
              <div>
                <p className="text-xs text-text-tertiary mb-2">反复错误点</p>
                <div className="flex gap-2 flex-wrap">
                  {report.risk_summary.repeated_errors.map((e) => (
                    <Badge key={e.name} variant="warning">{e.name} ({e.error_count}次)</Badge>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )}

        <Card className="mb-4">
          <CardTitle>各学科风险概览</CardTitle>
          <p className="text-xs text-text-tertiary mb-3">以下是各学科的整体状态，具体薄弱知识点已由系统自动安排复习</p>
          <div className="space-y-3">
            {report.subject_risks.map((sr) => {
              const risk = riskLevelLabels[sr.risk_level];
              return (
                <div key={sr.subject_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-sm">{sr.subject_name}</span>
                    <Badge className={risk ? `${risk.color} bg-transparent` : ""}>{risk?.label}</Badge>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {report.action_suggestions.length > 0 && (
          <Card className="mb-4">
            <CardTitle>关注建议</CardTitle>
            <ul className="space-y-2">
              {report.action_suggestions.map((s, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-text-primary">
                  <span className="text-primary">•</span>
                  {s}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {/* Parent Support Suggestions */}
        {report.parent_support_suggestions && report.parent_support_suggestions.length > 0 && (
          <Card className="mb-4">
            <CardTitle>家长支持建议</CardTitle>
            <ul className="space-y-2">
              {report.parent_support_suggestions.map((s, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-text-primary">
                  <span className="text-warning">•</span>
                  {s}
                </li>
              ))}
            </ul>
          </Card>
        )}

        <div className="text-center py-4">
          <p className="text-xs text-text-tertiary">
            家长视角仅展示趋势和风险概览，不包含具体题目、排名等敏感信息
          </p>
        </div>
      </main>
    </div>
  );
}
