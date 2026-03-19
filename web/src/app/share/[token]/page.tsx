"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/ui/skeleton";
import { riskLevelLabels, formatMinutes } from "@/lib/utils";
import { mockShareReport } from "@/lib/mock-data";

export default function ShareReportPage() {
  const params = useParams();
  const [loading, setLoading] = useState(true);
  const [expired, setExpired] = useState(false);
  const report = mockShareReport;

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  if (loading) return (
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

  if (expired) return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <Card className="text-center max-w-sm">
        <p className="text-4xl mb-4">⏰</p>
        <h2 className="text-lg font-semibold mb-2">链接已过期</h2>
        <p className="text-sm text-text-secondary">此分享链接已超过有效期，请联系学生获取新的分享链接</p>
      </Card>
    </div>
  );

  return (
    <div className="min-h-screen bg-bg">
      <div className="max-w-2xl mx-auto px-4 py-6 md:py-8">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center text-white font-bold mx-auto mb-3">AI</div>
          <h1 className="text-xl font-bold text-text-primary">{report.student_nickname}的学习周报</h1>
          <p className="text-sm text-text-secondary mt-1">{report.week} · 由 AI 伴学教练生成</p>
        </div>

        {/* Summary Metrics */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">学习天数</p>
            <p className="text-xl font-bold">{report.usage_days}/7</p>
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">总时长</p>
            <p className="text-xl font-bold">{formatMinutes(report.total_minutes)}</p>
          </Card>
          <Card className="text-center">
            <p className="text-xs text-text-tertiary">完成率</p>
            <p className="text-xl font-bold">{report.task_completion_rate}%</p>
          </Card>
        </div>

        {/* Subject Summaries */}
        <Card className="mb-4">
          <CardTitle>各学科概览</CardTitle>
          <div className="space-y-3">
            {report.subject_summaries.map((s) => {
              const risk = riskLevelLabels[s.risk_level];
              return (
                <div key={s.subject} className="p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-sm">{s.subject}</span>
                    {risk && <Badge className={`${risk.color} bg-transparent`}>{risk.label}</Badge>}
                  </div>
                  <p className="text-sm text-text-secondary">{s.summary}</p>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Suggestions */}
        <Card className="mb-6">
          <CardTitle>建议</CardTitle>
          <ul className="space-y-2">
            {report.suggestions.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-text-primary">
                <span className="text-primary">•</span>{s}
              </li>
            ))}
          </ul>
        </Card>

        {/* Footer */}
        <div className="text-center space-y-2">
          <p className="text-xs text-text-tertiary">生成时间：{new Date(report.generated_at).toLocaleDateString("zh-CN")}</p>
          <p className="text-xs text-text-tertiary">此报告为摘要版本，不包含原始题目图片、完整答疑记录和排名信息</p>
          <p className="text-xs text-text-tertiary">链接有效期 7 天</p>
        </div>
      </div>
    </div>
  );
}
