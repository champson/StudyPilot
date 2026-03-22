"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/app-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { Modal } from "@/components/ui/modal";
import { cn, entryReasonLabels, errorTypeLabels } from "@/lib/utils";
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
  if (e.last_recall_result === "success") return { label: "召回成功", color: "text-success bg-success-light" };
  if (e.last_recall_result === "fail") return { label: "召回失败", color: "text-error bg-error-light" };
  if (!e.is_recalled) return { label: "待召回", color: "text-error bg-error-light" };
  return { label: "待召回", color: "text-error bg-error-light" };
}

export default function ErrorsPage() {
  const [selectedSubject, setSelectedSubject] = useState<string>("all");
  const [selectedFilter, setSelectedFilter] = useState<ErrorFilter>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selectedError, setSelectedError] = useState<ErrorBookItem | null>(null);
  
  // Practice mode state
  const [practiceMode, setPracticeMode] = useState(false);
  const [practiceErrors, setPracticeErrors] = useState<ErrorBookItem[]>([]);
  const [currentPracticeIndex, setCurrentPracticeIndex] = useState(0);
  const [practiceResults, setPracticeResults] = useState<{ mastered: number; needsReview: number }>({ mastered: 0, needsReview: 0 });
  const [practiceComplete, setPracticeComplete] = useState(false);
  const [practiceLoading, setPracticeLoading] = useState(false);
  
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

  async function startSinglePractice(error: ErrorBookItem) {
    try {
      await api.post(`/student/errors/${error.id}/recall`);
      setPracticeErrors([error]);
      setCurrentPracticeIndex(0);
      setPracticeResults({ mastered: 0, needsReview: 0 });
      setPracticeComplete(false);
      setPracticeMode(true);
      setSelectedError(null);
    } catch {
      toast("进入召回练习失败", "error");
    }
  }

  // Start practice mode
  async function startPractice() {
    setPracticeLoading(true);
    try {
      // Fetch all unrecalled errors for practice
      const data = await api.get<{ items: ErrorBookItem[]; total: number }>(
        "/student/errors?is_recalled=false&page_size=50"
      );
      const unrecalledErrors = (data.items || []).slice(0, 20);
      
      if (unrecalledErrors.length === 0) {
        toast("没有待召回的错题", "info");
        return;
      }

      // Call batch-recall API to schedule these errors
      const errorIds = unrecalledErrors.map(e => e.id);
      await api.post("/student/errors/batch-recall", { error_ids: errorIds });

      setPracticeErrors(unrecalledErrors);
      setCurrentPracticeIndex(0);
      setPracticeResults({ mastered: 0, needsReview: 0 });
      setPracticeComplete(false);
      setPracticeMode(true);
    } catch {
      toast("加载失败，请重试", "error");
    } finally {
      setPracticeLoading(false);
    }
  }

  // Handle practice answer
  async function handlePracticeAnswer(mastered: boolean) {
    const currentError = practiceErrors[currentPracticeIndex];
    if (!currentError) return;

    try {
      await api.post(`/student/errors/${currentError.id}/recall-result`, {
        result: mastered ? "success" : "fail"
      });
      
      setPracticeResults(prev => ({
        mastered: prev.mastered + (mastered ? 1 : 0),
        needsReview: prev.needsReview + (mastered ? 0 : 1),
      }));

      if (currentPracticeIndex < practiceErrors.length - 1) {
        setCurrentPracticeIndex(prev => prev + 1);
      } else {
        setPracticeComplete(true);
        mutateErrors();
        mutateSummary();
      }
    } catch {
      toast("提交失败，请重试", "error");
    }
  }

  // Exit practice mode
  function exitPractice() {
    setPracticeMode(false);
    setPracticeErrors([]);
    setCurrentPracticeIndex(0);
    setPracticeResults({ mastered: 0, needsReview: 0 });
    setPracticeComplete(false);
    mutateErrors();
    mutateSummary();
  }

  const subjectTabs = [
    { value: "all" as const, label: "全部", count: summary?.total ?? 0 },
    ...(summary?.by_subject.map((s) => ({ value: s.subject_name, label: s.subject_name, count: s.count })) || []),
  ];

  if (isLoading && !errorsData) return <><PageHeader title="错题本" backHref="/dashboard" /><div className="max-w-4xl mx-auto px-4 py-4 space-y-4"><CardSkeleton /><CardSkeleton /><CardSkeleton /></div></>;

  // Practice Mode Full Screen UI
  if (practiceMode) {
    const currentError = practiceErrors[currentPracticeIndex];
    const progress = ((currentPracticeIndex + (practiceComplete ? 1 : 0)) / practiceErrors.length) * 100;

    return (
      <div className="fixed inset-0 bg-bg z-50 flex flex-col">
        {/* Header */}
        <div className="bg-card border-b border-border px-4 py-3">
          <div className="max-w-3xl mx-auto flex items-center justify-between">
            <button
              onClick={exitPractice}
              className="text-text-secondary hover:text-text-primary transition-colors"
            >
              ✕ 退出练习
            </button>
            <span className="text-sm font-medium">
              召回练习 {currentPracticeIndex + 1} / {practiceErrors.length}
            </span>
            <div className="w-20" />
          </div>
          {/* Progress Bar */}
          <div className="max-w-3xl mx-auto mt-3">
            <div
              className="h-2 bg-gray-200 rounded-full overflow-hidden"
              role="progressbar"
              aria-valuenow={Math.round(progress)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={"召回练习进度"}
            >
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-8">
            {practiceComplete ? (
              // Summary View
              <div className="text-center py-12">
                <div className="text-6xl mb-6">🎉</div>
                <h2 className="text-2xl font-bold text-text-primary mb-4">练习完成！</h2>
                <div className="flex justify-center gap-8 mb-8">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-success">{practiceResults.mastered}</div>
                    <div className="text-sm text-text-secondary">已掌握</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-error">{practiceResults.needsReview}</div>
                    <div className="text-sm text-text-secondary">仍需复习</div>
                  </div>
                </div>
                <p className="text-text-secondary mb-8">
                  共完成 {practiceErrors.length} 道错题的召回练习
                </p>
                <Button variant="primary" onClick={exitPractice}>
                  返回错题本
                </Button>
              </div>
            ) : currentError ? (
              // Question View
              <div>
                <Card className="mb-6">
                  <div className="flex items-center gap-2 mb-4">
                    <span>{getSubject(currentError.subject_id).icon}</span>
                    <span className="font-medium">{getSubject(currentError.subject_id).name}</span>
                    {currentError.error_type && (
                      <Badge className="bg-error-light text-error ml-auto">
                        {errorTypeLabels[currentError.error_type] || currentError.error_type}
                      </Badge>
                    )}
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg mb-4">
                    <p className="text-text-primary leading-relaxed whitespace-pre-wrap">
                      {currentError.question_content.text || "暂无题目文本"}
                    </p>
                  </div>
                  <div className="text-sm text-text-secondary">
                    <p>知识点：{currentError.knowledge_points.map(k => k.name).join("、") || "暂无"}</p>
                  </div>
                </Card>

                <div className="text-center">
                  <p className="text-text-secondary mb-6">请回顾这道题，然后标记你的掌握情况</p>
                  <div className="flex justify-center gap-4">
                    <Button
                      variant="outline"
                      size="lg"
                      onClick={() => handlePracticeAnswer(false)}
                      className="min-w-[120px]"
                    >
                      🤔 仍需复习
                    </Button>
                    <Button
                      variant="primary"
                      size="lg"
                      onClick={() => handlePracticeAnswer(true)}
                      className="min-w-[120px]"
                    >
                      ✅ 已掌握
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg">
      <PageHeader title="错题本" backHref="/dashboard" />

      <main className="max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-6">
        {/* Subject Tabs */}
        <div
          className="flex gap-1 overflow-x-auto pb-2 mb-4 -mx-4 px-4 md:mx-0 md:px-0"
          role="group"
          aria-label="学科筛选"
        >
          {subjectTabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => { setSelectedSubject(tab.value); setPage(1); }}
              aria-pressed={selectedSubject === tab.value}
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
        <div
          className="flex items-center gap-3 mb-4 flex-wrap"
          role="group"
          aria-label="筛选条件"
        >
          <select
            value={selectedFilter}
            onChange={(e) => { setSelectedFilter(e.target.value as ErrorFilter); setPage(1); }}
            className="px-3 py-2 border border-border rounded-lg text-sm bg-card"
            aria-label="状态筛选"
          >
            {FILTER_OPTIONS.map((s) => <option key={s.value} value={s.value}>状态：{s.label}</option>)}
          </select>
          <div className="flex-1 min-w-[200px]">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索题目或知识点..."
              aria-label="搜索题目或知识点"
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
              <Button 
                size="sm" 
                variant="danger" 
                onClick={startPractice}
                disabled={practiceLoading}
              >
                {practiceLoading ? "加载中..." : "开始召回练习"}
              </Button>
            </div>
          </Card>
        )}

        {/* Error List */}
        {filteredErrors.length === 0 ? (
          <EmptyState icon="📭" title="暂无符合条件的错题" description="试试调整筛选条件" />
        ) : (
          <div className="space-y-3" role="list" aria-label="错题列表">
            {filteredErrors.map((error) => {
              const status = getStatusDisplay(error);
              const subject = getSubject(error.subject_id);
              const questionText = error.question_content.text || "无题目文本";
              return (
                <Card
                  key={error.id}
                  role="listitem"
                  aria-label={`${subject.name}错题: ${questionText.slice(0, 30)}${questionText.length > 30 ? "..." : ""}`}
                >
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
                    <Button variant="outline" size="sm" onClick={() => setSelectedError(error)}>查看详情</Button>
                    {error.last_recall_result !== "success" && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => startSinglePractice(error)}
                      >
                        {error.last_recall_result === "fail" ? "再次召回" : "开始召回"}
                      </Button>
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

        {/* Error Detail Modal */}
        <Modal
          isOpen={!!selectedError}
          onClose={() => setSelectedError(null)}
          title="错题详情"
          size="lg"
          footer={
            <div className="flex justify-end gap-2">
              {selectedError && selectedError.last_recall_result !== "success" && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    if (selectedError) {
                      startSinglePractice(selectedError);
                    }
                  }}
                >
                  开始召回
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => setSelectedError(null)}>
                关闭
              </Button>
            </div>
          }
        >
          {selectedError && (
            <div className="space-y-4">
              {/* Question Content */}
              <div>
                <h4 className="text-sm font-medium text-text-secondary mb-2">题目内容</h4>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-text-primary leading-relaxed whitespace-pre-wrap">
                    {selectedError.question_content.text || "暂无题目文本"}
                  </p>
                  {selectedError.question_image_url && (
                    <div className="mt-3 p-2 bg-gray-100 rounded text-center text-text-tertiary text-sm">
                      [题目图片]
                    </div>
                  )}
                </div>
              </div>

              {/* Error Type */}
              {selectedError.error_type && (
                <div>
                  <h4 className="text-sm font-medium text-text-secondary mb-2">错误类型</h4>
                  <Badge className="bg-error-light text-error">
                    {errorTypeLabels[selectedError.error_type] || selectedError.error_type}
                  </Badge>
                </div>
              )}

              {/* Knowledge Points */}
              <div>
                <h4 className="text-sm font-medium text-text-secondary mb-2">关联知识点</h4>
                <div className="flex flex-wrap gap-2">
                  {selectedError.knowledge_points.length > 0 ? (
                    selectedError.knowledge_points.map((kp, idx) => (
                      <Badge key={idx} className="bg-blue-50 text-blue-600">
                        {kp.name}
                      </Badge>
                    ))
                  ) : (
                    <p className="text-sm text-text-tertiary">暂无关联知识点</p>
                  )}
                </div>
              </div>

              {/* AI Explanation */}
              <div>
                <h4 className="text-sm font-medium text-text-secondary mb-2">AI 讲解</h4>
                <div className="p-4 bg-blue-50 rounded-lg">
                  {selectedError.is_explained ? (
                    <p className="text-sm text-text-primary leading-relaxed">
                      此题已完成 AI 讲解。如需查看完整讲解记录，请前往答疑历史中查找。
                    </p>
                  ) : (
                    <p className="text-sm text-text-tertiary">
                      此题尚未进行 AI 讲解。点击「开始召回」进入练习流程。
                    </p>
                  )}
                </div>
              </div>

              {/* Recall Status */}
              {selectedError.last_recall_at && (
                <div>
                  <h4 className="text-sm font-medium text-text-secondary mb-2">召回记录</h4>
                  <p className="text-sm text-text-primary">
                    最近召回：{selectedError.last_recall_result === "success" ? "✅ 成功" : "❌ 失败"}
                    {" · "}
                    {new Date(selectedError.last_recall_at).toLocaleDateString("zh-CN")}
                    {selectedError.recall_count > 1 && ` · 已召回 ${selectedError.recall_count} 次`}
                  </p>
                </div>
              )}
            </div>
          )}
        </Modal>
      </main>
    </div>
  );
}
