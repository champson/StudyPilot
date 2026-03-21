"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { CorrectionDetail } from "@/types/api";

const OCR_REASONS = ["图片模糊", "手写识别错误", "格式复杂", "其他"];

interface OcrCorrectionPanelProps {
  detail: CorrectionDetail;
  onSubmit: (correctedContent: { text: string }, reason: string) => Promise<void>;
  onSkip: () => void;
}

export function OcrCorrectionPanel({ detail, onSubmit, onSkip }: OcrCorrectionPanelProps) {
  const [text, setText] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const ctx = detail.context || {};
  const originalUrl = typeof ctx.original_url === "string" ? ctx.original_url : null;
  const ocrError = typeof ctx.ocr_error === "string" ? ctx.ocr_error : null;

  async function handleSubmit() {
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      await onSubmit({ text: text.trim() }, reason);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      {originalUrl ? (
        <div>
          <p className="text-xs text-text-tertiary mb-2">原始图片</p>
          <div className="border border-border rounded-lg overflow-hidden bg-gray-50 max-h-64 flex items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={originalUrl} alt="原始上传" className="max-w-full max-h-64 object-contain" />
          </div>
        </div>
      ) : null}

      {ctx.ocr_result != null ? (
        <div>
          <p className="text-xs text-text-tertiary mb-2">当前 OCR 结果</p>
          <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-x-auto border border-border max-h-32">
            {JSON.stringify(ctx.ocr_result, null, 2)}
          </pre>
        </div>
      ) : null}

      {ocrError ? (
        <div>
          <p className="text-xs text-error mb-1">OCR 错误</p>
          <p className="text-xs text-text-secondary">{ocrError}</p>
        </div>
      ) : null}

      <div>
        <p className="text-xs text-text-tertiary mb-2">修正内容</p>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="输入修正后的文本..."
          rows={4}
          className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </div>

      <div>
        <p className="text-xs text-text-tertiary mb-2">修正原因</p>
        <select
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-card"
        >
          <option value="">选择原因（可选）</option>
          {OCR_REASONS.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-2 pt-2">
        <Button size="sm" onClick={handleSubmit} disabled={!text.trim() || submitting}>
          {submitting ? "提交中..." : "提交修正"}
        </Button>
        <Button variant="outline" size="sm" onClick={onSkip}>跳过</Button>
      </div>
    </div>
  );
}
