"use client";

import { useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { Card, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { usePendingCorrections, useCorrectionDetail } from "@/lib/hooks";
import { api } from "@/lib/api";
import type { CorrectionItem } from "@/types/api";
import { OcrCorrectionPanel } from "@/components/admin/ocr-correction-panel";
import { KnowledgeCorrectionPanel } from "@/components/admin/knowledge-correction-panel";
import { CorrectionLogList } from "@/components/admin/correction-log-list";

const TYPE_TABS = [
  { value: "all", label: "全部" },
  { value: "ocr", label: "OCR 纠偏" },
  { value: "knowledge", label: "知识点纠偏" },
  { value: "plan", label: "计划纠偏" },
  { value: "qa", label: "答疑纠偏" },
];

export default function CorrectionsPage() {
  const [selectedType, setSelectedType] = useState("all");
  const [page] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const { toast } = useToast();
  const { data: correctionsData, isLoading, mutate } = usePendingCorrections(page);
  const { data: detail } = useCorrectionDetail(selectedId);

  const corrections: CorrectionItem[] = correctionsData?.items || [];
  const filtered = corrections.filter((c) => selectedType === "all" || c.target_type === selectedType);

  async function handleResolve(correctedContent: Record<string, unknown>, reason?: string) {
    if (!selectedId) return;
    try {
      await api.post(`/admin/corrections/${selectedId}/resolve`, {
        corrected_content: correctedContent,
        reason: reason || undefined,
      });
      setSelectedId(null);
      mutate();
      toast("纠偏已处理", "success");
    } catch {
      toast("操作失败", "error");
    }
  }

  async function handleQuickResolve(item: CorrectionItem) {
    // For non-OCR items that already have valid content, quick resolve
    try {
      await api.post(`/admin/corrections/${item.id}/resolve`);
      mutate();
      toast("纠偏已处理", "success");
    } catch {
      toast("操作失败，请查看详情后修正", "error");
      setSelectedId(item.id);
    }
  }

  return (
    <AdminLayout>
      <div className="p-4 md:p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">人工纠偏</h2>
          <Button variant="outline" size="sm" onClick={() => setShowLogs(!showLogs)}>
            {showLogs ? "返回待处理" : "修正记录"}
          </Button>
        </div>

        {showLogs ? (
          <Card>
            <CardTitle>修正历史记录</CardTitle>
            <CorrectionLogList />
          </Card>
        ) : (
          <>
            <div className="flex gap-1 overflow-x-auto">
              {TYPE_TABS.map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => setSelectedType(tab.value)}
                  className={cn(
                    "px-4 py-2 rounded-lg text-sm whitespace-nowrap transition-colors",
                    selectedType === tab.value ? "bg-primary text-white" : "bg-card border border-border text-text-secondary hover:bg-gray-50"
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {isLoading ? (
              <div className="space-y-3"><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>
            ) : filtered.length === 0 ? (
              <EmptyState icon="✅" title="暂无待处理纠偏" description="系统运行正常" />
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Left: List */}
                <div className="space-y-3">
                  {filtered.map((item) => (
                    <div
                      key={item.id}
                      role="button"
                      tabIndex={0}
                      className={cn(
                        "p-4 bg-card rounded-xl border cursor-pointer transition-all",
                        selectedId === item.id ? "ring-2 ring-primary border-primary" : "border-border hover:border-primary/40"
                      )}
                      onClick={() => setSelectedId(item.id)}
                      onKeyDown={(e) => { if (e.key === "Enter") setSelectedId(item.id); }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Badge variant={item.target_type === "ocr" ? "warning" : item.target_type === "knowledge" ? "error" : "primary"}>
                            {item.target_type.toUpperCase()}
                          </Badge>
                          <span className="text-sm text-text-secondary">#{item.target_id}</span>
                        </div>
                        <span className="text-xs text-text-tertiary">{new Date(item.created_at).toLocaleString("zh-CN")}</span>
                      </div>
                      {item.correction_reason && (
                        <p className="text-sm text-text-primary line-clamp-2">{item.correction_reason}</p>
                      )}
                      <div className="flex items-center gap-2 mt-2">
                        {item.target_type !== "ocr" && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleQuickResolve(item);
                            }}
                          >
                            快速处理
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedId(item.id);
                          }}
                        >
                          查看详情
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Right: Detail panel */}
                <div>
                  {selectedId && detail ? (
                    <Card className="sticky top-4">
                      <CardTitle>
                        {detail.target_type === "ocr" ? "OCR 纠偏" : detail.target_type === "knowledge" ? "知识点纠偏" : detail.target_type === "qa" ? "答疑纠偏" : "计划纠偏"}
                        <span className="text-text-tertiary font-normal ml-2">#{detail.id}</span>
                      </CardTitle>

                      {detail.target_type === "ocr" && (
                        <OcrCorrectionPanel
                          detail={detail}
                          onSubmit={async (content, reason) => {
                            await handleResolve(content, reason);
                          }}
                          onSkip={() => setSelectedId(null)}
                        />
                      )}

                      {detail.target_type === "knowledge" && (
                        <KnowledgeCorrectionPanel
                          detail={detail}
                          onSubmit={async (content, reason) => {
                            await handleResolve(content, reason);
                          }}
                          onSkip={() => setSelectedId(null)}
                        />
                      )}

                      {detail.target_type === "plan" && (
                        <div className="space-y-4">
                          {detail.context && (
                            <div>
                              <p className="text-xs text-text-tertiary mb-2">计划信息</p>
                              <div className="p-3 bg-gray-50 rounded-lg space-y-1.5">
                                <p className="text-sm"><span className="text-text-tertiary">日期：</span>{String(detail.context.plan_date)}</p>
                                <p className="text-sm"><span className="text-text-tertiary">模式：</span>{String(detail.context.learning_mode)}</p>
                              </div>
                              {Array.isArray(detail.context.tasks) && (
                                <div className="mt-3">
                                  <p className="text-xs text-text-tertiary mb-2">任务列表</p>
                                  <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-x-auto border border-border max-h-48">
                                    {JSON.stringify(detail.context.tasks, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          )}
                          <div className="flex items-center gap-2">
                            <Button size="sm" onClick={() => handleResolve(detail.corrected_content)}>
                              确认并处理
                            </Button>
                            <Button variant="outline" size="sm" onClick={() => setSelectedId(null)}>跳过</Button>
                          </div>
                        </div>
                      )}

                      {detail.target_type === "qa" && (
                        <div className="space-y-4">
                          {detail.original_content && (
                            <div>
                              <p className="text-xs text-text-tertiary mb-2">答疑信息</p>
                              <div className="p-3 bg-gray-50 rounded-lg space-y-1.5">
                                <p className="text-sm">
                                  <span className="text-text-tertiary">触发原因：</span>
                                  {String(detail.original_content.alert_type)}
                                </p>
                                <p className="text-sm">
                                  <span className="text-text-tertiary">会话ID：</span>
                                  #{detail.target_id}
                                </p>
                              </div>
                            </div>
                          )}
                          {detail.correction_reason && (
                            <div>
                              <p className="text-xs text-text-tertiary mb-2">纠偏原因</p>
                              <p className="text-sm bg-gray-50 p-3 rounded-lg">{detail.correction_reason}</p>
                            </div>
                          )}
                          <div className="flex items-center gap-2">
                            <Button size="sm" onClick={() => handleResolve(detail.corrected_content || {})}>
                              确认已处理
                            </Button>
                            <Button variant="outline" size="sm" onClick={() => setSelectedId(null)}>跳过</Button>
                          </div>
                        </div>
                      )}
                    </Card>
                  ) : (
                    <Card className="flex items-center justify-center min-h-[200px]">
                      <p className="text-sm text-text-tertiary">选择左侧纠偏项查看详情</p>
                    </Card>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </AdminLayout>
  );
}
