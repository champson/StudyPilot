"use client";

import { useParams } from "next/navigation";
import useSWR from "swr";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/ui/skeleton";
import { riskLevelLabels, formatMinutes } from "@/lib/utils";
import type { ShareReport } from "@/types/api";
import { env } from "@/lib/env";

// Direct fetch without auth for public share links
async function fetchShare(path: string): Promise<ShareReport> {
  const res = await fetch(`${env.NEXT_PUBLIC_API_BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: { code: "UNKNOWN" } }));
    throw { status: res.status, code: body.error?.code || "UNKNOWN" };
  }
  const json = await res.json();
  return json.data;
}

export default function ShareReportPage() {
  const params = useParams();
  const token = params.token as string;

  const { data: report, error, isLoading } = useSWR(
    token ? `/share/${token}` : null,
    fetchShare
  );

  if (isLoading) return (
    <div className="min-h-screen bg-bg">
      <div className="max-w-2xl mx-auto px-4 py-8">
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center text-white font-bold mx-auto mb-3">AI</div>
          <p className="text-sm text-text-tertiary">加载中...</p>
        </div>
        <PageSkeleton />
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <Card className="text-center max-w-sm">
        <p className="text-4xl mb-4">⏰</p>
        <h2 className="text-lg font-semibold mb-2">链接已过期或无效</h2>
        <p className="text-sm text-text-secondary">此分享链接已超过有效期或无效，请联系学生获取新的分享链接</p>
      </Card>
    </div>
  );

  if (!report) return null;

  return (
    <div className="min-h-screen bg-bg">
      <div className="max-w-2xl mx-auto px-4 py-6 md:py-8">
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center text-white font-bold mx-auto mb-3">AI</div>
          <h1 className="text-xl font-bold text-text-primary">{report.student_name}的学习周报</h1>
          <p className="text-sm text-text-secondary mt-1">{report.report_week} · 由 AI 伴学教练生成</p>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-6">
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">学习天数</p>
            <p className="text-xl font-bold">{report.usage_days}/7</p>
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">总时长</p>
            <p className="text-xl font-bold">{formatMinutes(report.total_minutes ?? 0)}</p>
          </Card>
        </div>

        {report.trend_overview && (
          <Card className="mb-4">
            <CardTitle>趋势概览</CardTitle>
            <p className="text-sm text-text-primary leading-relaxed">{report.trend_overview}</p>
          </Card>
        )}

        <Card className="mb-4">
          <CardTitle>各学科概览</CardTitle>
          <div className="space-y-3">
            {report.subject_risk_overview.map((s) => {
              const risk = riskLevelLabels[s.risk_level];
              return (
                <div key={s.subject_name} className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
                  <span className="font-medium text-sm">{s.subject_name}</span>
                  {risk && <Badge className={`${risk.color} bg-transparent`}>{risk.label}</Badge>}
                </div>
              );
            })}
          </div>
        </Card>

        {report.next_stage_suggestions_summary && (
          <Card className="mb-6">
            <CardTitle>建议</CardTitle>
            <p className="text-sm text-text-primary leading-relaxed">{report.next_stage_suggestions_summary}</p>
          </Card>
        )}

        <div className="text-center space-y-2">
          {report.expires_at && (
            <p className="text-xs text-text-tertiary">有效期至：{new Date(report.expires_at).toLocaleDateString("zh-CN")}</p>
          )}
          <p className="text-xs text-text-tertiary">此报告为摘要版本，不包含原始题目图片、完整答疑记录和排名信息</p>
        </div>
      </div>
    </div>
  );
}
