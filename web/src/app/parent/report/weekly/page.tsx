"use client";

import { PageHeader } from "@/components/layout/app-header";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { riskLevelLabels, formatMinutes } from "@/lib/utils";
import { useParentWeeklyReport } from "@/lib/hooks";

export default function ParentWeeklyReportPage() {
  const { data: report, isLoading } = useParentWeeklyReport();

  if (isLoading) return <><PageHeader title="孩子学习周报" /><PageSkeleton /></>;
  if (!report) return <><PageHeader title="孩子学习周报" /><div className="max-w-4xl mx-auto px-4 py-12"><EmptyState icon="📊" title="暂无周报数据" description="孩子完成一周学习后将自动生成" /></div></>;

  return (
    <div className="min-h-screen bg-bg">
      <PageHeader title="孩子学习周报（家长视角）" rightContent={
        <span className="text-sm text-text-secondary">{report.report_week}</span>
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
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">总时长</p>
            <p className="text-xl font-bold">{formatMinutes(report.total_minutes ?? 0)}</p>
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">完成率</p>
            <p className="text-xl font-bold">{Math.round((report.task_completion_rate ?? 0) * 100)}%</p>
          </Card>
        </div>

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

        <div className="text-center py-4">
          <p className="text-xs text-text-tertiary">
            家长视角仅展示趋势和风险概览，不包含具体题目、排名等敏感信息
          </p>
        </div>
      </main>
    </div>
  );
}
