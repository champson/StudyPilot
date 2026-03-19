"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppHeader } from "@/components/layout/app-header";
import { Card, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProgressRing } from "@/components/ui/progress-ring";
import { CardSkeleton } from "@/components/ui/skeleton";
import { mockDailyPlan, mockRecentUploads, mockQAHistory, mockErrorSummary, mockWeeklyReport } from "@/lib/mock-data";
import { formatRelativeTime, formatMinutes, modeLabels, uploadTypeLabels } from "@/lib/utils";

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState("workday_follow");
  const router = useRouter();
  const plan = mockDailyPlan;
  const uploads = mockRecentUploads;
  const qaHistory = mockQAHistory;
  const errorSummary = mockErrorSummary;

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  const progressPercent = plan.total_tasks > 0 ? Math.round((plan.completed_tasks / plan.total_tasks) * 100) : 0;

  return (
    <div className="min-h-screen bg-bg">
      <AppHeader showMode currentMode={mode} onModeChange={setMode} />

      <main className="max-w-7xl mx-auto px-4 md:px-6 py-4 md:py-6">
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton />
          </div>
        ) : (
          <>
            {/* Top row: Plan + Upload */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              {/* Today's Plan Card */}
              <Card>
                <CardTitle>📅 今日计划</CardTitle>
                <div className="flex items-start gap-4">
                  <ProgressRing percent={progressPercent} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text-secondary mb-2">今日推荐 {plan.recommended_subjects.length} 门学科</p>
                    <div className="space-y-1.5">
                      {plan.recommended_subjects.map((s) => (
                        <div key={s.name} className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                          <span className="text-sm font-medium">{s.name}</span>
                          <span className="text-xs text-text-tertiary">{s.reasons[0]}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <p className="text-xs text-text-tertiary mt-3">已完成 {plan.completed_tasks}/{plan.total_tasks} 个任务</p>

                {plan.source === "history_inferred" && (
                  <div className="mt-2 px-3 py-1.5 bg-warning-light rounded-lg text-xs text-warning flex items-center gap-1">
                    <span>⚠️</span> 基于历史推断生成
                  </div>
                )}

                <Button className="mt-4" fullWidth onClick={() => router.push("/plan/today")}>
                  {plan.completed_tasks > 0 ? "▶ 继续学习" : "▶ 开始学习"}
                </Button>
              </Card>

              {/* Upload Entry Card */}
              <Card>
                <CardTitle>📤 上传学习内容</CardTitle>
                <button
                  onClick={() => router.push("/upload")}
                  className="w-full py-8 border-2 border-dashed border-border rounded-xl hover:border-primary hover:bg-primary-light/30 transition-colors flex flex-col items-center gap-2 mb-4"
                >
                  <span className="text-3xl">📷</span>
                  <span className="text-sm text-text-secondary">拍照上传</span>
                  <span className="text-xs text-text-tertiary">点击拍照或选择图片</span>
                </button>

                <div className="flex gap-2 mb-4">
                  <button onClick={() => router.push("/upload")} className="flex-1 py-2.5 border border-border rounded-lg text-sm text-text-secondary hover:bg-gray-50 transition-colors">📝 文本输入</button>
                  <button onClick={() => router.push("/upload")} className="flex-1 py-2.5 border border-border rounded-lg text-sm text-text-secondary hover:bg-gray-50 transition-colors">🎤 语音输入</button>
                </div>

                <div className="space-y-2">
                  <p className="text-xs text-text-tertiary">最近上传：</p>
                  {uploads.slice(0, 2).map((u) => (
                    <div key={u.id} className="flex items-center gap-2 text-xs text-text-secondary">
                      <span>·</span>
                      <span>{u.subject}{uploadTypeLabels[u.upload_type]}</span>
                      <span className="text-text-tertiary">{formatRelativeTime(u.created_at)}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            {/* Bottom row: QA + Error Book */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              {/* QA Entry Card */}
              <Card>
                <CardTitle>💬 实时答疑</CardTitle>
                <p className="text-sm text-text-secondary mb-4">遇到不会的题？立即提问</p>
                <Button fullWidth onClick={() => router.push("/qa")}>🎯 开始答疑</Button>

                <div className="mt-4 space-y-2">
                  <p className="text-xs text-text-tertiary">最近答疑：</p>
                  {qaHistory.slice(0, 2).map((q) => (
                    <Link key={q.id} href={`/qa`} className="flex items-center gap-2 text-xs text-text-secondary hover:text-primary transition-colors">
                      <span>·</span>
                      <span>{q.title}</span>
                      <span className="text-text-tertiary">- {formatRelativeTime(q.created_at)}</span>
                    </Link>
                  ))}
                </div>
              </Card>

              {/* Error Book Entry Card */}
              <Card>
                <CardTitle>📕 错题本</CardTitle>
                <p className="text-sm text-text-secondary mb-3">待处理错题</p>
                <div className="flex gap-2 flex-wrap mb-4">
                  {Object.entries(errorSummary.by_subject).map(([subject, count]) => (
                    <div key={subject} className="flex flex-col items-center px-3 py-2 bg-gray-50 rounded-lg min-w-[48px]">
                      <span className="text-xs text-text-tertiary">{subject}</span>
                      <span className="text-lg font-semibold text-text-primary">{count}</span>
                    </div>
                  ))}
                </div>

                {errorSummary.pending_recall_count > 0 && (
                  <div className="flex items-center gap-2 mb-4 text-sm">
                    <span className="w-2 h-2 rounded-full bg-error animate-pulse" />
                    <span className="text-error font-medium">{errorSummary.pending_recall_count} 道错题待召回</span>
                  </div>
                )}

                <Button variant="outline" fullWidth onClick={() => router.push("/errors")}>进入错题本</Button>
              </Card>
            </div>

            {/* Weekly Summary Bar */}
            <Card className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">📊</span>
                <span className="font-medium">本周学习概况</span>
              </div>
              <div className="flex items-center gap-4 md:gap-6 text-sm text-text-secondary flex-wrap">
                <span>本周学习 <strong className="text-text-primary">{mockWeeklyReport.usage_days}</strong> 天</span>
                <span className="hidden md:inline text-border">│</span>
                <span>累计 <strong className="text-text-primary">{formatMinutes(mockWeeklyReport.total_minutes)}</strong></span>
                <span className="hidden md:inline text-border">│</span>
                <span>完成率 <strong className="text-text-primary">{mockWeeklyReport.task_completion_rate}%</strong></span>
                <span className="hidden md:inline text-border">│</span>
                <span>错题修复 <strong className="text-text-primary">{mockWeeklyReport.fixed_errors}</strong> 道</span>
              </div>
              <Link href="/report/weekly" className="text-sm text-primary hover:underline whitespace-nowrap">
                查看周报 →
              </Link>
            </Card>
          </>
        )}
      </main>
    </div>
  );
}
