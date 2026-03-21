"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { CorrectionDetail } from "@/types/api";

const KNOWLEDGE_STATUSES = ["未观察", "初步接触", "基本掌握", "需要巩固", "反复失误"];

interface KnowledgeCorrectionPanelProps {
  detail: CorrectionDetail;
  onSubmit: (correctedContent: { status: string }, reason: string) => Promise<void>;
  onSkip: () => void;
}

export function KnowledgeCorrectionPanel({ detail, onSubmit, onSkip }: KnowledgeCorrectionPanelProps) {
  const [status, setStatus] = useState((detail.corrected_content as Record<string, string>)?.status || "");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const ctx = detail.context || {};
  const subjectName = typeof ctx.subject_name === "string" ? ctx.subject_name : null;
  const kpName = typeof ctx.knowledge_point_name === "string" ? ctx.knowledge_point_name : null;
  const currentStatus = typeof ctx.current_status === "string" ? ctx.current_status : null;

  async function handleSubmit() {
    if (!status) return;
    setSubmitting(true);
    try {
      await onSubmit({ status }, reason);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs text-text-tertiary mb-2">知识点信息</p>
        <div className="p-3 bg-gray-50 rounded-lg space-y-1.5">
          {subjectName ? (
            <p className="text-sm"><span className="text-text-tertiary">学科：</span>{subjectName}</p>
          ) : null}
          {kpName ? (
            <p className="text-sm"><span className="text-text-tertiary">知识点：</span>{kpName}</p>
          ) : null}
          {currentStatus ? (
            <p className="text-sm"><span className="text-text-tertiary">当前状态：</span>{currentStatus}</p>
          ) : null}
        </div>
      </div>

      <div>
        <p className="text-xs text-text-tertiary mb-2">修正为</p>
        <div className="space-y-2">
          {KNOWLEDGE_STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={cn(
                "w-full text-left px-3 py-2 rounded-lg text-sm border transition-colors",
                status === s ? "border-primary bg-primary-light/50 text-primary font-medium" : "border-border hover:bg-gray-50"
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs text-text-tertiary mb-2">修正原因</p>
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="输入修正原因（可选）"
          className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </div>

      <div className="flex items-center gap-2 pt-2">
        <Button size="sm" onClick={handleSubmit} disabled={!status || submitting}>
          {submitting ? "提交中..." : "提交修正"}
        </Button>
        <Button variant="outline" size="sm" onClick={onSkip}>跳过</Button>
      </div>
    </div>
  );
}
