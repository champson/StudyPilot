"use client";

import { useState, useEffect } from "react";
import { AdminLayout } from "@/components/layout/admin-layout";
import { Card, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { mockCorrections } from "@/lib/mock-data";
import type { CorrectionItem } from "@/types/api";

const TYPE_TABS = [
  { value: "all", label: "全部" },
  { value: "ocr", label: "OCR 纠偏" },
  { value: "knowledge", label: "知识点纠偏" },
  { value: "plan", label: "计划纠偏" },
  { value: "qa", label: "答疑纠偏" },
];

const STATUS_BADGES: Record<string, { label: string; variant: "default" | "success" | "warning" }> = {
  pending: { label: "待处理", variant: "warning" },
  resolved: { label: "已处理", variant: "success" },
  dismissed: { label: "已忽略", variant: "default" },
};

export default function CorrectionsPage() {
  const [corrections, setCorrections] = useState<CorrectionItem[]>(mockCorrections);
  const [selectedType, setSelectedType] = useState("all");
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 400);
    return () => clearTimeout(timer);
  }, []);

  const filtered = corrections.filter((c) => selectedType === "all" || c.type === selectedType);

  function handleResolve(id: number) {
    setCorrections((prev) => prev.map((c) => c.id === id ? { ...c, status: "resolved" as const } : c));
    toast("纠偏已处理", "success");
  }

  function handleDismiss(id: number) {
    setCorrections((prev) => prev.map((c) => c.id === id ? { ...c, status: "dismissed" as const } : c));
    toast("已忽略", "info");
  }

  return (
    <AdminLayout>
      <div className="p-4 md:p-6 space-y-4">
        <h2 className="text-xl font-bold">人工纠偏</h2>

        {/* Type Tabs */}
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

        {/* Corrections List */}
        {loading ? (
          <div className="space-y-3">{[1, 2, 3].map((i) => <div key={i} className="skeleton h-32 rounded-xl" />)}</div>
        ) : filtered.length === 0 ? (
          <EmptyState icon="✅" title="暂无待处理纠偏" description="系统运行正常" />
        ) : (
          <div className="space-y-3">
            {filtered.map((item) => {
              const statusInfo = STATUS_BADGES[item.status];
              return (
                <Card key={item.id}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Badge variant={item.type === "ocr" ? "warning" : item.type === "knowledge" ? "error" : "primary"}>
                        {item.type.toUpperCase()}
                      </Badge>
                      <span className="text-sm text-text-secondary">{item.student_name}</span>
                      <span className="text-xs text-text-tertiary">·</span>
                      <span className="text-xs text-text-tertiary">{new Date(item.created_at).toLocaleString("zh-CN")}</span>
                    </div>
                    <Badge variant={statusInfo?.variant}>{statusInfo?.label}</Badge>
                  </div>

                  <p className="text-sm text-text-primary mb-3">{item.description}</p>

                  {item.original_data && Object.keys(item.original_data).length > 0 && (
                    <div className="p-2.5 bg-gray-50 rounded-lg mb-3">
                      <p className="text-xs text-text-tertiary mb-1">原始数据：</p>
                      <pre className="text-xs text-text-secondary overflow-x-auto">{JSON.stringify(item.original_data, null, 2)}</pre>
                    </div>
                  )}

                  {item.corrected_data && (
                    <div className="p-2.5 bg-success-light rounded-lg mb-3">
                      <p className="text-xs text-success mb-1">修正数据：</p>
                      <pre className="text-xs text-text-secondary overflow-x-auto">{JSON.stringify(item.corrected_data, null, 2)}</pre>
                    </div>
                  )}

                  {item.status === "pending" && (
                    <div className="flex items-center gap-2 pt-3 border-t border-border-light">
                      <Button size="sm" onClick={() => handleResolve(item.id)}>标记已处理</Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDismiss(item.id)}>忽略</Button>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
