"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppHeader } from "@/components/layout/app-header";
import { Card, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ProgressRing } from "@/components/ui/progress-ring";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useDailyPlan, useRecentUploads, useQAHistory, useErrorSummary, useWeeklyReport } from "@/lib/hooks";
import { formatRelativeTime, formatMinutes, modeLabels, uploadTypeLabels } from "@/lib/utils";
import { getSubject } from "@/lib/subjects";
import { api } from "@/lib/api";
import { getStoredAuth } from "@/lib/auth";
import type { StudyUpload, QASession, PlanTask } from "@/types/api";
import { useToast } from "@/components/ui/toast";
import { useRecentWeeks } from "@/components/report/week-selector";

export default function DashboardPage() {
  const [mode, setMode] = useState("workday_follow");
  const router = useRouter();
  const { toast } = useToast();
  const [generating, setGenerating] = useState(false);

  const { data: plan, isLoading: planLoading, mutate: mutatePlan } = useDailyPlan();
  const { data: uploadsData } = useRecentUploads(1, 3);
  const { data: qaData } = useQAHistory(1, 3);
  const { data: errorSummary } = useErrorSummary();
  const recentWeeks = useRecentWeeks();
  const currentWeek = recentWeeks[0]?.value ?? null;
  const { data: weeklyReport } = useWeeklyReport(currentWeek);

  // Sync mode from server when plan loads
  useEffect(() => {
    if (plan?.learning_mode) setMode(plan.learning_mode);
  }, [plan?.learning_mode]);

  const uploads: StudyUpload[] = uploadsData?.items || [];
  const qaHistory: QASession[] = qaData?.items || [];

  const tasks: PlanTask[] = plan?.tasks || [];
  const completedCount = tasks.filter((t) => t.status === "completed").length;
  const totalCount = tasks.length;
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  async function handleModeChange(newMode: string) {
    const prevMode = mode;
    setMode(newMode);
    try {
      await api.patch("/student/plan/mode", { learning_mode: newMode });
      mutatePlan();
    } catch {
      setMode(prevMode);
      toast("切换模式失败", "error");
    }
  }

  async function handleGeneratePlan() {
    setGenerating(true);
    try {
      await api.post("/student/plan/generate", {});
      mutatePlan();
      toast("今日计划已生成", "success");
    } catch {
      toast("生成失败，请重试", "error");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="min-h-screen bg-bg">
      <AppHeader showMode currentMode={mode} onModeChange={handleModeChange} userName={getStoredAuth()?.userName} />

      <main className="max-w-7xl mx-auto px-4 md:px-6 py-4 md:py-6">
        {planLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton />
          </div>
        ) : (
          <>
            {/* Top row: Plan + Upload */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              {/* Today's Plan Card */}
              <Card>
                <CardTitle>今日计划</CardTitle>
                {plan ? (
                  <>
                    <div className="flex items-start gap-4">
                      <ProgressRing percent={progressPercent} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-text-secondary mb-2">今日 {totalCount} 个任务</p>
                        <p className="text-xs text-text-tertiary">模式：{modeLabels[plan.learning_mode]}</p>
                      </div>
                    </div>

                    <p className="text-xs text-text-tertiary mt-3">已完成 {completedCount}/{totalCount} 个任务</p>

                    {plan.is_history_inferred && (
                      <div className="mt-2 px-3 py-1.5 bg-warning-light rounded-lg text-xs text-warning flex items-center gap-1">
                        <span>⚠️</span> 基于历史推断生成
                      </div>
                    )}

                    <Button className="mt-4" fullWidth onClick={() => router.push("/plan/today")}>
                      {completedCount > 0 ? "继续学习" : "开始学习"}
                    </Button>
                  </>
                ) : (
                  <div className="text-center py-6">
                    <p className="text-sm text-text-secondary mb-4">还没有今日计划</p>
                    <Button onClick={handleGeneratePlan} loading={generating}>
                      生成今日计划
                    </Button>
                  </div>
                )}
              </Card>

              {/* Upload Entry Card */}
              <Card>
                <CardTitle>上传学习内容</CardTitle>
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

                {uploads.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs text-text-tertiary">最近上传：</p>
                    {uploads.slice(0, 2).map((u) => (
                      <div key={u.id} className="flex items-center gap-2 text-xs text-text-secondary">
                        <span>·</span>
                        <span>{getSubject(u.subject_id ?? 0).name}{uploadTypeLabels[u.upload_type]}</span>
                        <span className="text-text-tertiary">{formatRelativeTime(u.created_at)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>

            {/* Bottom row: QA + Error Book */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              {/* QA Entry Card */}
              <Card>
                <CardTitle>实时答疑</CardTitle>
                <p className="text-sm text-text-secondary mb-4">遇到不会的题？立即提问</p>
                <Button fullWidth onClick={() => router.push("/qa")}>开始答疑</Button>

                {qaHistory.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <p className="text-xs text-text-tertiary">最近答疑：</p>
                    {qaHistory.slice(0, 2).map((q) => (
                      <Link key={q.id} href="/qa" className="flex items-center gap-2 text-xs text-text-secondary hover:text-primary transition-colors">
                        <span>·</span>
                        <span>答疑会话 ({q.message_count} 条消息)</span>
                        <span className="text-text-tertiary">- {formatRelativeTime(q.created_at)}</span>
                      </Link>
                    ))}
                  </div>
                )}
              </Card>

              {/* Error Book Entry Card */}
              <Card>
                <CardTitle>错题本</CardTitle>
                {errorSummary ? (
                  <>
                    <p className="text-sm text-text-secondary mb-3">待处理错题</p>
                    <div className="flex gap-2 flex-wrap mb-4">
                      {errorSummary.by_subject.map((s) => (
                        <div key={s.subject_name} className="flex flex-col items-center px-3 py-2 bg-gray-50 rounded-lg min-w-[48px]">
                          <span className="text-xs text-text-tertiary">{s.subject_name}</span>
                          <span className="text-lg font-semibold text-text-primary">{s.count}</span>
                        </div>
                      ))}
                    </div>

                    {errorSummary.unrecalled > 0 && (
                      <div className="flex items-center gap-2 mb-4 text-sm">
                        <span className="w-2 h-2 rounded-full bg-error animate-pulse" />
                        <span className="text-error font-medium">{errorSummary.unrecalled} 道错题待召回</span>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-sm text-text-secondary mb-4">暂无错题记录</p>
                )}

                <Button variant="outline" fullWidth onClick={() => router.push("/errors")}>进入错题本</Button>
              </Card>
            </div>

            {/* Weekly Summary Bar */}
            {weeklyReport && (
              <Card className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-lg">📊</span>
                  <span className="font-medium">本周学习概况</span>
                </div>
                <div className="flex items-center gap-4 md:gap-6 text-sm text-text-secondary flex-wrap">
                  <span>本周学习 <strong className="text-text-primary">{weeklyReport.usage_days}</strong> 天</span>
                  <span className="hidden md:inline text-border">│</span>
                  <span>累计 <strong className="text-text-primary">{formatMinutes(weeklyReport.total_minutes ?? 0)}</strong></span>
                  <span className="hidden md:inline text-border">│</span>
                  <span>完成率 <strong className="text-text-primary">{Math.round((weeklyReport.task_completion_rate ?? 0) * 100)}%</strong></span>
                </div>
                <Link href="/report/weekly" className="text-sm text-primary hover:underline whitespace-nowrap">
                  查看周报 →
                </Link>
              </Card>
            )}
          </>
        )}
      </main>
    </div>
  );
}
