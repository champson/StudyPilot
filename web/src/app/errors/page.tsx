"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/app-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { cn, entryReasonLabels } from "@/lib/utils";
import { mockErrors, mockErrorSummary } from "@/lib/mock-data";
import { getSubject } from "@/lib/subjects";
import type { ErrorBookItem } from "@/types/api";

type ErrorFilter = "all" | "not_explained" | "explained_not_recalled" | "recalled";

const FILTER_OPTIONS: { value: ErrorFilter; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "not_explained", label: "未讲解" },
  { value: "explained_not_recalled", label: "待召回" },
  { value: "recalled", label: "已召回" },
];

function matchesFilter(e: ErrorBookItem, filter: ErrorFilter): boolean {
  if (filter === "all") return true;
  if (filter === "not_explained") return !e.is_explained;
  if (filter === "explained_not_recalled") return e.is_explained && !e.is_recalled;
  if (filter === "recalled") return e.is_recalled;
  return true;
}

function getStatusDisplay(e: ErrorBookItem): { label: string; color: string } {
  if (!e.is_explained) return { label: "未讲解", color: "text-text-secondary bg-gray-100" };
  if (!e.is_recalled) return { label: "待召回", color: "text-error bg-error-light" };
  if (e.last_recall_result === "success") return { label: "召回成功", color: "text-success bg-success-light" };
  return { label: "召回失败", color: "text-error bg-error-light" };
}

export default function ErrorsPage() {
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState<ErrorBookItem[]>(mockErrors);
  const [selectedSubject, setSelectedSubject] = useState<string>("all");
  const [selectedFilter, setSelectedFilter] = useState<ErrorFilter>("all");
  const [search, setSearch] = useState("");
  const router = useRouter();
  const { toast } = useToast();
  const summary = mockErrorSummary;

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  const filteredErrors = errors.filter((e) => {
    if (selectedSubject !== "all" && getSubject(e.subject_id).name !== selectedSubject) return false;
    if (!matchesFilter(e, selectedFilter)) return false;
    const text = e.question_content.text ?? "";
    if (search && !text.includes(search) && !e.knowledge_points.some((k) => k.name.includes(search))) return false;
    return true;
  });

  function handleRecall(errorId: number) {
    setErrors((prev) =>
      prev.map((e) => e.id === errorId ? { ...e, is_recalled: true, last_recall_at: new Date().toISOString(), last_recall_result: "success", recall_count: e.recall_count + 1 } : e)
    );
    toast("召回练习完成", "success");
  }

  const subjectTabs = [
    { value: "all" as const, label: "全部", count: summary.total },
    ...summary.by_subject.map((s) => ({ value: s.subject_name, label: s.subject_name, count: s.count })),
  ];

  if (loading) return <><PageHeader title="错题本" backHref="/dashboard" /><div className="max-w-4xl mx-auto px-4 py-4 space-y-4"><CardSkeleton /><CardSkeleton /><CardSkeleton /></div></>;

  return (
    <div className="min-h-screen bg-bg">
      <PageHeader title="错题本" backHref="/dashboard" />

      <main className="max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-6">
        {/* Subject Tabs */}
        <div className="flex gap-1 overflow-x-auto pb-2 mb-4 -mx-4 px-4 md:mx-0 md:px-0">
          {subjectTabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setSelectedSubject(tab.value)}
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
            onChange={(e) => setSelectedFilter(e.target.value as ErrorFilter)}
            className="px-3 py-2 border border-border rounded-lg text-sm bg-card"
          >
            {FILTER_OPTIONS.map((s) => <option key={s.value} value={s.value}>状态：{s.label}</option>)}
          </select>
          <select className="px-3 py-2 border border-border rounded-lg text-sm bg-card">
            <option>排序：最新入库</option>
            <option>排序：最久未复习</option>
          </select>
          <div className="flex-1 min-w-[200px]">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="🔍 搜索题目或知识点..."
              className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
        </div>

        {/* Recall Banner */}
        {summary.unrecalled > 0 && (
          <Card className="mb-4 bg-error-light border-error/20">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-error">🔔 待召回提醒</p>
                <p className="text-sm text-text-secondary mt-1">
                  你有 <strong className="text-error">{summary.unrecalled}</strong> 道错题需要再次召回，巩固后可提升掌握度
                </p>
              </div>
              <Button size="sm" variant="danger">🔄 开始召回练习</Button>
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

                  {error.question_image_url && (
                    <div className="w-40 h-28 bg-gray-100 rounded-lg mb-3 flex items-center justify-center text-text-tertiary text-xs">[题目图片]</div>
                  )}

                  <div className="space-y-1.5 mb-3">
                    <p className="text-xs text-text-secondary">📚 知识点：{error.knowledge_points.map((k) => k.name).join("、")}</p>
                    <p className="text-xs text-text-secondary">❌ 错误类型：{error.error_type}</p>
                    <p className="text-xs text-text-secondary">📥 入库原因：{entryReasonLabels[error.entry_reason]}</p>
                  </div>

                  {error.last_recall_at && (
                    <p className="text-xs text-text-tertiary mb-3">
                      ✅ 召回结果：{error.last_recall_result === "success" ? "成功" : "失败"} · {new Date(error.last_recall_at).toLocaleDateString("zh-CN")}
                    </p>
                  )}

                  <div className="flex items-center gap-2 pt-3 border-t border-border-light">
                    <p className="text-xs text-text-tertiary flex-1">入库时间：{new Date(error.created_at).toLocaleDateString("zh-CN")}</p>
                    <Button variant="outline" size="sm" onClick={() => router.push("/qa")}>📖 查看讲解</Button>
                    {!error.is_recalled && (
                      <Button variant="primary" size="sm" onClick={() => handleRecall(error.id)}>🔄 再次召回</Button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}

        {filteredErrors.length > 0 && (
          <div className="text-center py-8">
            <button className="text-sm text-text-tertiary hover:text-primary transition-colors">加载更多...</button>
          </div>
        )}
      </main>
    </div>
  );
}
