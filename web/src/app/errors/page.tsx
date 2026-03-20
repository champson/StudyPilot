"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/app-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { cn, entryReasonLabels } from "@/lib/utils";
import { getSubject } from "@/lib/subjects";
import { useErrorList, useErrorSummary } from "@/lib/hooks";
import { api } from "@/lib/api";
import type { ErrorBookItem } from "@/types/api";

type ErrorFilter = "all" | "not_recalled" | "recalled";

const FILTER_OPTIONS: { value: ErrorFilter; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "not_recalled", label: "待召回" },
  { value: "recalled", label: "已召回" },
];

function getStatusDisplay(e: ErrorBookItem): { label: string; color: string } {
  if (!e.is_explained) return { label: "未讲解", color: "text-text-secondary bg-gray-100" };
  if (!e.is_recalled) return { label: "待召回", color: "text-error bg-error-light" };
  if (e.last_recall_result === "success") return { label: "召回成功", color: "text-success bg-success-light" };
  return { label: "召回失败", color: "text-error bg-error-light" };
}

export default function ErrorsPage() {
  const [selectedSubject, setSelectedSubject] = useState<string>("all");
  const [selectedFilter, setSelectedFilter] = useState<ErrorFilter>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const router = useRouter();
  const { toast } = useToast();

  const { data: summary, mutate: mutateSummary } = useErrorSummary();
  const isRecalled = selectedFilter === "recalled" ? true : selectedFilter === "not_recalled" ? false : undefined;
  const subjectId = selectedSubject !== "all"
    ? summary?.by_subject.find(s => s.subject_name === selectedSubject)?.subject_id
    : undefined;

  const { data: errorsData, isLoading, mutate: mutateErrors } = useErrorList({
    subject_id: subjectId,
    is_recalled: isRecalled,
    page,
    page_size: 20,
  });

  const errors: ErrorBookItem[] = errorsData?.items || [];
  const total = errorsData?.total || 0;

  // Client-side search filter (on top of server-side filters)
  const filteredErrors = search
    ? errors.filter((e) => {
        const text = e.question_content.text ?? "";
        return text.includes(search) || e.knowledge_points.some((k) => k.name.includes(search));
      })
    : errors;

  async function handleRecall(errorId: number, result: "correct" | "incorrect" | "partial" = "correct") {
    try {
      await api.post(`/student/errors/${errorId}/recall`, { result });
      mutateErrors();
      mutateSummary();
      toast("召回练习完成", "success");
    } catch {
      toast("操作失败", "error");
    }
  }

  const subjectTabs = [
    { value: "all" as const, label: "全部", count: summary?.total ?? 0 },
    ...(summary?.by_subject.map((s) => ({ value: s.subject_name, label: s.subject_name, count: s.count })) || []),
  ];

  if (isLoading && !errorsData) return <><PageHeader title="错题本" backHref="/dashboard" /><div className="max-w-4xl mx-auto px-4 py-4 space-y-4"><CardSkeleton /><CardSkeleton /><CardSkeleton /></div></>;

  return (
    <div className="min-h-screen bg-bg">
      <PageHeader title="错题本" backHref="/dashboard" />

      <main className="max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-6">
        {/* Subject Tabs */}
        <div className="flex gap-1 overflow-x-auto pb-2 mb-4 -mx-4 px-4 md:mx-0 md:px-0">
          {subjectTabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => { setSelectedSubject(tab.value); setPage(1); }}
              className={cn(
                "px-4 py-2 rounded-lg text-sm whitespace-nowrap transition-colors shrink-0",
                selectedSubject === tab.value
                  ? "bg-primary text-white font-medium"
                  : "bg-card border border-border text-text-secondary hover:bg-gray-50"
              )}
            >
              {tab.label}({tab.count})
            </button>
          ))}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <select
            value={selectedFilter}
            onChange={(e) => { setSelectedFilter(e.target.value as ErrorFilter); setPage(1); }}
            className="px-3 py-2 border border-border rounded-lg text-sm bg-card"
          >
            {FILTER_OPTIONS.map((s) => <option key={s.value} value={s.value}>状态：{s.label}</option>)}
          </select>
          <div className="flex-1 min-w-[200px]">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索题目或知识点..."
              className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
        </div>

        {/* Recall Banner */}
        {summary && summary.unrecalled > 0 && (
          <Card className="mb-4 bg-error-light border-error/20">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-error">待召回提醒</p>
                <p className="text-sm text-text-secondary mt-1">
                  你有 <strong className="text-error">{summary.unrecalled}</strong> 道错题需要再次召回
                </p>
              </div>
              <Button size="sm" variant="danger" onClick={() => { setSelectedFilter("not_recalled"); setPage(1); }}>开始召回练习</Button>
            </div>
          </Card>
        )}

        {/* Error List */}
        {filteredErrors.length === 0 ? (
          <EmptyState icon="📭" title="暂无符合条件的错题" description="试试调整筛选条件" />
        ) : (
          <div className="space-y-3">
            {filteredErrors.map((error) => {
              const status = getStatusDisplay(error);
              const subject = getSubject(error.subject_id);
              return (
                <Card key={error.id}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span>{subject.icon}</span>
                      <span className="font-medium text-sm">{subject.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={status.color}>{status.label}</Badge>
                      {error.is_explained && !error.is_recalled && <span className="w-2 h-2 rounded-full bg-error animate-pulse" />}
                    </div>
                  </div>

                  <p className="text-sm text-text-primary mb-3 leading-relaxed">{error.question_content.text}</p>

                  <div className="space-y-1.5 mb-3">
                    <p className="text-xs text-text-secondary">知识点：{error.knowledge_points.map((k) => k.name).join("、")}</p>
                    {error.error_type && <p className="text-xs text-text-secondary">错误类型：{error.error_type}</p>}
                    <p className="text-xs text-text-secondary">入库原因：{entryReasonLabels[error.entry_reason]}</p>
                  </div>

                  {error.last_recall_at && (
                    <p className="text-xs text-text-tertiary mb-3">
                      召回结果：{error.last_recall_result === "success" ? "成功" : "失败"} · {new Date(error.last_recall_at).toLocaleDateString("zh-CN")}
                    </p>
                  )}

                  <div className="flex items-center gap-2 pt-3 border-t border-border-light">
                    <p className="text-xs text-text-tertiary flex-1">入库时间：{new Date(error.created_at).toLocaleDateString("zh-CN")}</p>
                    <Button variant="outline" size="sm" onClick={() => router.push("/qa")}>查看讲解</Button>
                    {!error.is_recalled && (
                      <div className="flex items-center gap-1">
                        <Button variant="primary" size="sm" onClick={() => handleRecall(error.id, "correct")}>已掌握</Button>
                        <Button variant="outline" size="sm" onClick={() => handleRecall(error.id, "partial")}>部分掌握</Button>
                        <Button variant="outline" size="sm" onClick={() => handleRecall(error.id, "incorrect")}>未掌握</Button>
                      </div>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {total > 20 && (
          <div className="flex justify-center gap-2 py-6">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</Button>
            <span className="text-sm text-text-secondary self-center">第 {page} 页</span>
            <Button variant="outline" size="sm" disabled={page * 20 >= total} onClick={() => setPage(p => p + 1)}>下一页</Button>
          </div>
        )}
      </main>
    </div>
  );
}
