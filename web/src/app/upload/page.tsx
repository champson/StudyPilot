"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/app-header";
import { Card, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { cn, uploadTypeLabels, formatRelativeTime } from "@/lib/utils";
import { mockRecentUploads } from "@/lib/mock-data";
import type { UploadType, Subject, OcrStatus } from "@/types/api";

const UPLOAD_TYPES: { value: UploadType; label: string; icon: string }[] = [
  { value: "note", label: "笔记", icon: "📝" },
  { value: "homework", label: "作业", icon: "📋" },
  { value: "test", label: "练习卷", icon: "📄" },
  { value: "handout", label: "讲义", icon: "📑" },
  { value: "score", label: "成绩", icon: "📊" },
];

const SUBJECTS: Subject[] = ["语文", "数学", "英语", "物理", "化学"];

interface PreviewImage {
  id: string;
  url: string;
  ocrStatus: OcrStatus;
}

export default function UploadPage() {
  const [selectedType, setSelectedType] = useState<UploadType>("homework");
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [note, setNote] = useState("");
  const [images, setImages] = useState<PreviewImage[]>([]);
  const [textContent, setTextContent] = useState("");
  const [inputMode, setInputMode] = useState<"photo" | "text" | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const { toast } = useToast();

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files) return;
    const newImages: PreviewImage[] = Array.from(files).slice(0, 9 - images.length).map((f) => ({
      id: Math.random().toString(36).slice(2),
      url: URL.createObjectURL(f),
      ocrStatus: "pending" as OcrStatus,
    }));
    setImages((prev) => [...prev, ...newImages]);
    setInputMode("photo");
  }

  function removeImage(id: string) {
    setImages((prev) => {
      const removed = prev.find((img) => img.id === id);
      if (removed) URL.revokeObjectURL(removed.url);
      return prev.filter((img) => img.id !== id);
    });
  }

  async function handleUpload() {
    if (!selectedType) { toast("请选择上传类型", "warning"); return; }
    if (images.length === 0 && !textContent) { toast("请上传图片或输入内容", "warning"); return; }

    setUploading(true);
    // Simulate OCR processing
    if (images.length > 0) {
      setImages((prev) => prev.map((img) => ({ ...img, ocrStatus: "processing" as OcrStatus })));
      await new Promise((r) => setTimeout(r, 1500));
      setImages((prev) => prev.map((img) => ({ ...img, ocrStatus: "completed" as OcrStatus })));
    }

    await new Promise((r) => setTimeout(r, 500));
    toast("上传成功", "success");
    setUploading(false);
    images.forEach((img) => URL.revokeObjectURL(img.url));
    setImages([]);
    setTextContent("");
    setNote("");
  }

  const ocrStatusConfig: Record<OcrStatus, { label: string; class: string }> = {
    pending: { label: "等待中", class: "text-text-tertiary" },
    processing: { label: "识别中", class: "text-primary" },
    completed: { label: "已识别", class: "text-success" },
    failed: { label: "识别失败", class: "text-error" },
  };

  return (
    <div className="min-h-screen bg-bg">
      <PageHeader title="上传学习内容" backHref="/dashboard" />

      <main className="max-w-4xl mx-auto px-4 md:px-6 py-4 md:py-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {/* Upload Method */}
          <Card>
            <CardTitle>选择上传方式</CardTitle>
            <button
              onClick={() => { setInputMode("photo"); fileInputRef.current?.click(); }}
              className="w-full py-10 border-2 border-dashed border-border rounded-xl hover:border-primary hover:bg-primary-light/30 transition-colors flex flex-col items-center gap-2 mb-4"
            >
              <span className="text-4xl">📷</span>
              <span className="text-sm font-medium text-text-primary">拍照上传</span>
              <span className="text-xs text-text-tertiary">点击拍照或选择图片</span>
            </button>
            <input ref={fileInputRef} type="file" accept="image/*" multiple className="hidden" onChange={handleFileSelect} />

            <div className="flex gap-2">
              <button
                onClick={() => setInputMode("text")}
                className={cn("flex-1 py-3 border rounded-lg text-sm transition-colors",
                  inputMode === "text" ? "border-primary bg-primary-light text-primary" : "border-border text-text-secondary hover:bg-gray-50"
                )}
              >
                📝 文本输入
              </button>
              <button className="flex-1 py-3 border border-border rounded-lg text-sm text-text-tertiary cursor-not-allowed">
                🎤 语音输入
              </button>
            </div>
          </Card>

          {/* Type + Subject */}
          <div className="space-y-4">
            <Card>
              <CardTitle>上传类型</CardTitle>
              <div className="flex gap-2 flex-wrap">
                {UPLOAD_TYPES.map((t) => (
                  <button
                    key={t.value}
                    onClick={() => setSelectedType(t.value)}
                    className={cn(
                      "flex flex-col items-center px-4 py-3 rounded-lg border-2 transition-colors min-w-[68px]",
                      selectedType === t.value ? "border-primary bg-primary-light text-primary" : "border-border hover:border-gray-300"
                    )}
                  >
                    <span className="text-xl mb-1">{t.icon}</span>
                    <span className="text-xs">{t.label}</span>
                  </button>
                ))}
              </div>
            </Card>

            <Card>
              <CardTitle>关联学科</CardTitle>
              <div className="flex gap-2 flex-wrap">
                {SUBJECTS.map((s) => (
                  <button
                    key={s}
                    onClick={() => setSelectedSubject(selectedSubject === s ? null : s)}
                    className={cn(
                      "px-4 py-2 rounded-lg text-sm border transition-colors",
                      selectedSubject === s ? "border-primary bg-primary-light text-primary font-medium" : "border-border text-text-secondary hover:bg-gray-50"
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>

              <div className="mt-3">
                <label className="block text-sm text-text-secondary mb-1">备注（可选）</label>
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="如：第三章课后习题"
                  className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </Card>
          </div>
        </div>

        {/* Text Input Area */}
        {inputMode === "text" && (
          <Card className="mb-4">
            <CardTitle>文本输入</CardTitle>
            <textarea
              value={textContent}
              onChange={(e) => setTextContent(e.target.value)}
              placeholder="请输入学习内容、题目或笔记..."
              rows={6}
              maxLength={2000}
              className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
            />
            <p className="text-xs text-text-tertiary text-right mt-1">{textContent.length}/2000</p>
          </Card>
        )}

        {/* Image Preview Area */}
        {images.length > 0 && (
          <Card className="mb-4">
            <CardTitle>上传预览</CardTitle>
            <div className="flex gap-3 flex-wrap">
              {images.map((img) => (
                <div key={img.id} className="relative w-28 h-28 rounded-lg overflow-hidden border border-border group">
                  <img src={img.url} alt="预览" className="w-full h-full object-cover" />
                  <div className="absolute inset-x-0 bottom-0 bg-black/50 text-center py-1">
                    <span className={cn("text-xs text-white", img.ocrStatus === "processing" ? "animate-pulse" : "")}>
                      {img.ocrStatus === "processing" ? "🔄 " : img.ocrStatus === "completed" ? "✓ " : ""}
                      {ocrStatusConfig[img.ocrStatus].label}
                    </span>
                  </div>
                  <button
                    onClick={() => removeImage(img.id)}
                    className="absolute top-1 right-1 w-5 h-5 bg-black/50 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    ×
                  </button>
                </div>
              ))}
              {images.length < 9 && (
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="w-28 h-28 border-2 border-dashed border-border rounded-lg flex flex-col items-center justify-center text-text-tertiary hover:border-primary hover:text-primary transition-colors"
                >
                  <span className="text-2xl">+</span>
                  <span className="text-xs">继续添加</span>
                </button>
              )}
            </div>

            <Button className="mt-4" fullWidth loading={uploading} onClick={handleUpload}>确认上传</Button>
          </Card>
        )}

        {inputMode === "text" && textContent && (
          <div className="mb-4">
            <Button fullWidth loading={uploading} onClick={handleUpload}>确认上传</Button>
          </div>
        )}

        {/* Upload History */}
        <Card>
          <div className="flex items-center justify-between mb-3">
            <CardTitle className="mb-0">📜 最近上传</CardTitle>
            <button className="text-xs text-primary hover:underline">查看全部 →</button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {mockRecentUploads.map((u) => (
              <div key={u.id} className="p-3 bg-gray-50 rounded-lg">
                <p className="text-sm font-medium">{u.subject}{uploadTypeLabels[u.upload_type]}</p>
                <p className="text-xs text-text-tertiary mt-1">{formatRelativeTime(u.created_at)}</p>
                <span className="text-xs text-success mt-1 inline-block">✓ 已识别</span>
              </div>
            ))}
          </div>
        </Card>
      </main>
    </div>
  );
}
