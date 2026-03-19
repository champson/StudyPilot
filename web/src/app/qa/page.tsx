"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/app-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { mockQAMessages, mockQAHistory } from "@/lib/mock-data";
import type { QAMessage, Subject } from "@/types/api";

const SUBJECTS: Subject[] = ["语文", "数学", "英语", "物理", "化学"];

const strategyLabels: Record<string, { label: string; class: string }> = {
  hint: { label: "提示", class: "bg-blue-50 text-blue-600" },
  step_by_step: { label: "分步讲解", class: "bg-purple-50 text-purple-600" },
  formula: { label: "公式提示", class: "bg-green-50 text-green-600" },
  full_solution: { label: "完整步骤", class: "bg-orange-50 text-orange-600" },
};

export default function QAPage() {
  const [messages, setMessages] = useState<QAMessage[]>(mockQAMessages);
  const [input, setInput] = useState("");
  const [subject, setSubject] = useState<Subject>("数学");
  const [sending, setSending] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef(false);
  const { toast } = useToast();
  const router = useRouter();

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  useEffect(() => {
    return () => { abortRef.current = true; };
  }, []);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || sending) return;
    const userMsg: QAMessage = {
      id: Date.now(),
      role: "user",
      content: input.trim(),
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);

    try {
      // Simulate streaming response
      await new Promise((r) => setTimeout(r, 800));
      if (abortRef.current) return;
      setSending(false);
      setStreaming(true);

      const responseText = "好的，让我来帮你分析这个问题。\n\n**📌 分析**\n这道题考查的是基础概念的理解和应用。\n\n**💡 思路**\n首先，我们需要明确题目中的已知条件，然后逐步推导。\n\n你先试着想一下第一步应该怎么做？";

      const aiMsg: QAMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: "",
        tutoring_strategy: "step_by_step",
        knowledge_points: ["相关知识点"],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, aiMsg]);

      // Simulate streaming
      for (let i = 0; i <= responseText.length; i++) {
        if (abortRef.current) break;
        await new Promise((r) => setTimeout(r, 20));
        if (abortRef.current) break;
        setMessages((prev) =>
          prev.map((m) => m.id === aiMsg.id ? { ...m, content: responseText.slice(0, i) } : m)
        );
      }
    } finally {
      if (!abortRef.current) {
        setSending(false);
        setStreaming(false);
      }
    }
  }, [input, sending]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <PageHeader
        title="实时答疑"
        backHref="/dashboard"
        rightContent={
          <div className="flex items-center gap-2">
            <Badge variant="primary">{subject}</Badge>
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="text-sm text-text-secondary hover:text-primary transition-colors"
            >
              历史会话
            </button>
          </div>
        }
      />

      {/* History Sidebar */}
      {showHistory && (
        <>
          <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setShowHistory(false)} />
          <div className="fixed right-0 top-14 bottom-0 w-72 bg-card border-l border-border z-50 p-4 overflow-y-auto">
            <h3 className="font-semibold mb-3">历史会话</h3>
            {mockQAHistory.map((s) => (
              <button
                key={s.id}
                className="w-full text-left p-3 rounded-lg hover:bg-gray-50 mb-1 transition-colors"
                onClick={() => setShowHistory(false)}
              >
                <p className="text-sm font-medium">{s.title}</p>
                <p className="text-xs text-text-tertiary">{s.subject} · {s.message_count}条消息</p>
              </button>
            ))}
          </div>
        </>
      )}

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4 max-w-3xl mx-auto w-full">
        <div className="space-y-4">
          {messages.map((msg) => (
            <div key={msg.id} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
              <div className={cn(
                "max-w-[85%] md:max-w-[75%] rounded-2xl px-4 py-3",
                msg.role === "user" ? "bg-primary text-white" : "bg-card border border-border"
              )}>
                {/* Strategy tag */}
                {msg.tutoring_strategy && (
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-text-secondary">🤖 AI 助教</span>
                    <span className={cn("text-xs px-2 py-0.5 rounded-md", strategyLabels[msg.tutoring_strategy]?.class)}>
                      {strategyLabels[msg.tutoring_strategy]?.label}
                    </span>
                  </div>
                )}

                {/* Attachments */}
                {msg.attachments?.map((url, i) => (
                  <div key={i} className="w-48 h-36 bg-gray-100 rounded-lg mb-2 flex items-center justify-center text-text-tertiary text-sm">
                    [题目图片]
                  </div>
                ))}

                {/* Content */}
                <div className={cn(
                  "text-sm whitespace-pre-wrap leading-relaxed",
                  msg.role === "user" ? "text-white" : "text-text-primary",
                  streaming && msg === messages[messages.length - 1] && msg.role === "assistant" && "streaming-cursor"
                )}>
                  {msg.content}
                </div>

                {/* Knowledge points */}
                {msg.knowledge_points && msg.knowledge_points.length > 0 && msg.content.length > 0 && !streaming && (
                  <div className="mt-3 pt-3 border-t border-border-light">
                    <p className="text-xs text-text-tertiary">📚 关联知识点：{msg.knowledge_points.join("、")}</p>
                  </div>
                )}
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex justify-start">
              <div className="bg-card border border-border rounded-2xl px-4 py-3">
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 bg-primary rounded-full animate-bounce" />
                  <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: "0.1s" }} />
                  <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Next Step Guide (shown after conversation) */}
        {messages.length > 4 && !streaming && !sending && (
          <div className="mt-4 p-3 bg-card border border-border rounded-xl">
            <p className="text-sm text-text-secondary mb-2">下一步</p>
            <div className="flex gap-2 flex-wrap">
              <Button variant="outline" size="sm">🔄 巩固练习</Button>
              <Button variant="outline" size="sm">📝 类似题</Button>
              <Button variant="outline" size="sm" onClick={() => document.querySelector("textarea")?.focus()}>❓ 继续追问</Button>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-border bg-card px-4 md:px-6 py-3">
        <div className="max-w-3xl mx-auto flex items-end gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2.5 text-text-secondary hover:text-primary hover:bg-gray-50 rounded-lg transition-colors shrink-0"
            aria-label="上传图片"
          >
            📷
          </button>
          <input ref={fileInputRef} type="file" accept="image/*" className="hidden" />

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题..."
            rows={1}
            className="flex-1 px-3 py-2.5 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none max-h-32"
            style={{ minHeight: "42px" }}
          />

          <button
            onClick={sendMessage}
            disabled={!input.trim() || sending || streaming}
            className={cn(
              "p-2.5 rounded-lg transition-colors shrink-0",
              input.trim() && !sending && !streaming ? "bg-primary text-white hover:bg-primary-hover" : "bg-gray-100 text-text-tertiary"
            )}
            aria-label="发送"
          >
            ➤
          </button>
        </div>
        <p className="text-xs text-text-tertiary text-center mt-1.5 max-w-3xl mx-auto">Enter 发送，Shift+Enter 换行</p>
      </div>
    </div>
  );
}
