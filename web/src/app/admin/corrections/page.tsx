"use client";

import { useState } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { usePendingCorrections } from "@/lib/hooks";
import { api } from "@/lib/api";
import type { CorrectionItem } from "@/types/api";

const TYPE_TABS = [
  { value: "all", label: "全部" },
  { value: "ocr", label: "OCR 纠偏" },
  { value: "knowledge", label: "知识点纠偏" },
  { value: "plan", label: "计划纠偏" },
];

const KNOWLEDGE_STATUSES = ["未观察", "初步接触", "需要巩固", "基本掌握", "反复失误"];


export default function CorrectionsPage() {
  const [selectedType, setSelectedType] = useState("all");
  const [page, setPage] = useState(1);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [correctedText, setCorrectedText] = useState("");
  const [knowledgeStatus, setKnowledgeStatus] = useState("");
  const { toast } = useToast();
  const { data: correctionsData, isLoading, mutate } = usePendingCorrections(page);

  const corrections: CorrectionItem[] = correctionsData?.items || [];
  const filtered = corrections.filter((c) => selectedType === "all" || c.target_type === selectedType);

  async function handleResolve(item: CorrectionItem) {
    // OCR corrections always require admin to provide real corrected text
    const hasRealOcrContent = item.target_type === "ocr"
      && item.corrected_content
      && "text" in item.corrected_content
      && item.corrected_content.text;
    if (item.target_type === "ocr" && !hasRealOcrContent && editingId !== item.id) {
      setEditingId(item.id);
      setCorrectedText("");
      toast("请先输入修正后的 OCR 文本", "error");
      return;
    }
    if (item.target_type === "ocr" && editingId === item.id && !correctedText.trim() && !hasRealOcrContent) {
      toast("请输入修正内容后再提交", "error");
      return;
    }
    // Knowledge corrections require a valid status
    if (item.target_type === "knowledge" && editingId === item.id && !knowledgeStatus) {
      toast("请选择修正后的知识点状态", "error");
      return;
    }
    try {
      const body: Record<string, unknown> = {};
      if (item.target_type === "ocr" && editingId === item.id && correctedText.trim()) {
        body.corrected_content = { text: correctedText.trim() };
      }
      if (item.target_type === "knowledge" && editingId === item.id && knowledgeStatus) {
        body.corrected_content = { status: knowledgeStatus };
      }
      await api.post(`/admin/corrections/${item.id}/resolve`, body);
      setEditingId(null);
      setCorrectedText("");
      setKnowledgeStatus("");
      mutate();
      toast("纠偏已处理", "success");
    } catch {
      toast("操作失败", "error");
    }
  }

  return (
    <AdminLayout>
      <div className="p-4 md:p-6 space-y-4">
        <h2 className="text-xl font-bold">人工纠偏</h2>

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
          <div className="space-y-3">
            {filtered.map((item) => (
                <Card key={item.id}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Badge variant={item.target_type === "ocr" ? "warning" : item.target_type === "knowledge" ? "error" : "primary"}>
                        {item.target_type.toUpperCase()}
                      </Badge>
                      <span className="text-sm text-text-secondary">目标 #{item.target_id}</span>
                      <span className="text-xs text-text-tertiary">·</span>
                      <span className="text-xs text-text-tertiary">{new Date(item.created_at).toLocaleString("zh-CN")}</span>
                    </div>
                    <Badge variant="warning">待处理</Badge>
                  </div>

                  {item.correction_reason && (
                    <p className="text-sm text-text-primary mb-3">原因：{item.correction_reason}</p>
                  )}

                  {item.original_content && Object.keys(item.original_content).length > 0 && (
                    <div className="p-2.5 bg-gray-50 rounded-lg mb-3">
                      <p className="text-xs text-text-tertiary mb-1">原始数据：</p>
                      <pre className="text-xs text-text-secondary overflow-x-auto">{JSON.stringify(item.original_content, null, 2)}</pre>
                    </div>
                  )}

                  {item.corrected_content && (
                    <div className="p-2.5 bg-success-light rounded-lg mb-3">
                      <p className="text-xs text-success mb-1">修正数据：</p>
                      <pre className="text-xs text-text-secondary overflow-x-auto">{JSON.stringify(item.corrected_content, null, 2)}</pre>
                    </div>
                  )}

                  {item.target_type === "ocr" && (
                    <div className="mb-3">
                      {editingId === item.id ? (
                        <textarea
                          value={correctedText}
                          onChange={(e) => setCorrectedText(e.target.value)}
                          placeholder="输入修正后的 OCR 文本..."
                          rows={4}
                          className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary/30"
                        />
                      ) : (
                        <Button variant="outline" size="sm" onClick={() => { setEditingId(item.id); setCorrectedText(""); }}>
                          输入修正内容
                        </Button>
                      )}
                    </div>
                  )}

                  {item.target_type === "knowledge" && (
                    <div className="mb-3">
                      {editingId === item.id ? (
                        <div className="space-y-2">
                          <p className="text-xs text-text-tertiary">修正知识点状态为：</p>
                          <select
                            value={knowledgeStatus}
                            onChange={(e) => setKnowledgeStatus(e.target.value)}
                            className="px-3 py-2 border border-border rounded-lg text-sm bg-card w-full"
                          >
                            <option value="">请选择状态</option>
                            {KNOWLEDGE_STATUSES.map((s) => (
                              <option key={s} value={s}>{s}</option>
                            ))}
                          </select>
                        </div>
                      ) : (
                        <Button variant="outline" size="sm" onClick={() => { setEditingId(item.id); setKnowledgeStatus((item.corrected_content as Record<string, string>)?.status || ""); }}>
                          修改状态
                        </Button>
                      )}
                    </div>
                  )}

                  <div className="flex items-center gap-2 pt-3 border-t border-border-light">
                    <Button size="sm" onClick={() => handleResolve(item)}>
                      {editingId === item.id ? "提交修正" : "标记已处理"}
                    </Button>
                    {editingId === item.id && (
                      <Button variant="outline" size="sm" onClick={() => { setEditingId(null); setCorrectedText(""); setKnowledgeStatus(""); }}>取消</Button>
                    )}
                  </div>
                </Card>
            ))}
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
