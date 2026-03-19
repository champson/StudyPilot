"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/app-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { mockDailyPlan } from "@/lib/mock-data";
import { cn, formatDate, getWeekday, taskTypeLabels, modeLabels } from "@/lib/utils";
import { getSubject } from "@/lib/subjects";
import type { PlanTask, TaskStatus } from "@/types/api";

export default function TodayPlanPage() {
  const [loading, setLoading] = useState(true);
  const [tasks, setTasks] = useState(mockDailyPlan.tasks);
  const router = useRouter();
  const { toast } = useToast();
  const plan = mockDailyPlan;

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  const completedCount = tasks.filter((t) => t.status === "completed").length;
  const progressPercent = tasks.length > 0 ? Math.round((completedCount / tasks.length) * 100) : 0;

  function updateTaskStatus(taskId: number, status: TaskStatus) {
    setTasks((prev) =>
      prev.map((t) =>
        t.id === taskId
          ? { ...t, status, ...(status === "completed" ? { completed_at: new Date().toISOString(), duration_minutes: t.estimated_minutes } : {}) }
          : t
      )
    );
    if (status === "completed") toast("任务已完成", "success");
  }

  const statusConfig: Record<TaskStatus, { label: string; dotClass: string; cardClass: string; lineClass: string }> = {
    completed: { label: "已完成", dotClass: "bg-success text-white", cardClass: "border-success/30 bg-success-light/30", lineClass: "bg-success" },
    executed: { label: "执行中", dotClass: "bg-primary text-white", cardClass: "border-primary/30", lineClass: "bg-primary" },
    entered: { label: "进行中", dotClass: "bg-primary text-white", cardClass: "border-primary/30", lineClass: "bg-primary" },
    pending: { label: "待开始", dotClass: "bg-gray-200 text-text-tertiary", cardClass: "border-dashed border-gray-200", lineClass: "bg-gray-200" },
  };

  if (loading) return <><PageHeader title="今日学习计划" backHref="/dashboard" /><PageSkeleton /></>;

  return (
    <div className="min-h-screen bg-bg">
      <PageHeader
        title="今日学习计划"
        backHref="/dashboard"
        rightContent={<Badge variant="primary">{modeLabels[plan.learning_mode]}</Badge>}
      />

      <main className="max-w-3xl mx-auto px-4 md:px-6 py-4 md:py-6">
        {/* Plan Overview */}
        <Card className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold">{formatDate(plan.plan_date)} {getWeekday(plan.plan_date)}</h2>
              <p className="text-sm text-text-secondary">可用时间：{plan.available_minutes} 分钟</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-text-secondary mb-1">总进度</p>
              <div className="flex items-center gap-2">
                <div className="w-32 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${progressPercent}%` }} />
                </div>
                <span className="text-sm font-medium">{progressPercent}%</span>
              </div>
            </div>
          </div>

          {plan.is_history_inferred && (
            <div className="mt-3 px-3 py-2 bg-warning-light rounded-lg text-xs text-warning flex items-center gap-1">
              ⚠️ 基于历史推断生成，建议上传今日学习内容以提升准确度
            </div>
          )}
        </Card>

        {/* Task Timeline */}
        <div className="relative">
          {tasks.map((task, i) => {
            const config = statusConfig[task.status];
            const taskType = taskTypeLabels[task.task_type];
            const subject = getSubject(task.subject_id);
            const content = task.task_content;

            return (
              <div key={task.id} className="relative pl-10 pb-6">
                {/* Timeline line */}
                {i < tasks.length - 1 && (
                  <div className={cn("absolute left-[15px] top-8 bottom-0 w-0.5", config.lineClass)} />
                )}
                {/* Timeline dot */}
                <div className={cn("absolute left-1.5 top-1.5 w-6 h-6 rounded-full flex items-center justify-center text-xs", config.dotClass)}>
                  {task.status === "completed" ? "✓" : task.sequence}
                </div>

                <Card className={cn("border", config.cardClass)}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span>{subject.icon}</span>
                      <span className="font-medium text-sm">{subject.name}</span>
                      <span className="text-text-tertiary text-sm">·</span>
                      <span className="text-sm text-text-secondary">{taskType?.label}</span>
                    </div>
                    <Badge variant={task.status === "completed" ? "success" : task.status === "pending" ? "default" : "primary"}>
                      {config.label}
                    </Badge>
                  </div>

                  <p className="text-sm text-text-primary mb-2">{content.description}</p>

                  {content.reasons && content.reasons.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap mb-2">
                      {content.reasons.map((r) => <Badge key={r} variant="warning">{r}</Badge>)}
                    </div>
                  )}

                  {task.status === "completed" ? (
                    <p className="text-xs text-text-tertiary">完成时间：{new Date(task.completed_at!).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })} · 用时 {task.duration_minutes} 分钟</p>
                  ) : task.status === "pending" ? (
                    <p className="text-xs text-text-tertiary">预计用时：{task.estimated_minutes} 分钟</p>
                  ) : (
                    <div className="flex items-center gap-2 mt-2">
                      <Button size="sm" onClick={() => updateTaskStatus(task.id, "completed")}>▶ 完成任务</Button>
                      <button onClick={() => router.push("/qa")} className="text-xs text-primary hover:underline">💬 发起答疑</button>
                    </div>
                  )}

                  {task.status === "pending" && i === completedCount + (tasks.some((t) => t.status === "entered" || t.status === "executed") ? 1 : 0) && (
                    <Button size="sm" className="mt-2" onClick={() => updateTaskStatus(task.id, "entered")}>▶ 开始学习</Button>
                  )}
                </Card>
              </div>
            );
          })}
        </div>

        {/* Low Input Prompt */}
        <Card className="mt-4 bg-primary-light/30 border-primary/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span>📤</span>
              <span className="text-sm text-text-secondary">今天还没上传学习内容？补充上传可以让计划更准确哦</span>
            </div>
            <Button variant="outline" size="sm" onClick={() => router.push("/upload")}>补充上传</Button>
          </div>
        </Card>
      </main>
    </div>
  );
}
