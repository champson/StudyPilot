"use client";

import { useState, useRef, useEffect, useCallback, useMemo, useId } from "react";
import { PageHeader } from "@/components/layout/app-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { getSubjectId } from "@/lib/subjects";
import { useQAHistory } from "@/lib/hooks";
import { streamRequest } from "@/lib/stream";
import type { QAMessage, Subject } from "@/types/api";

const strategyLabels: Record<string, { label: string; class: string }> = {
  hint: { label: "提示", class: "bg-blue-50 text-blue-600" },
  step_by_step: { label: "分步讲解", class: "bg-purple-50 text-purple-600" },
  formula: { label: "公式提示", class: "bg-green-50 text-green-600" },
  full_solution: { label: "完整步骤", class: "bg-orange-50 text-orange-600" },
};

// 长列表优化：最大可见消息数
const MAX_VISIBLE_MESSAGES = 50;
const LOAD_MORE_THRESHOLD = 100;

export default function QAPage() {
  const inputDescId = useId();
  const [showAllMessages, setShowAllMessages] = useState(false);
  const [messages, setMessages] = useState<QAMessage[]>([
    {
      id: 0,
      role: "assistant",
      content: "你好！我是你的 AI 学习助教，遇到不会的题可以随时问我。\n你可以直接输入问题，或者拍照上传题目。",
      created_at: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [subject] = useState<Subject>("数学");
  const [sending, setSending] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef(false);
  const { toast } = useToast();

  const { data: qaHistoryData } = useQAHistory(1, 20);
  const qaHistory = qaHistoryData?.items || [];

  // 长列表优化：超过阈值时只渲染最近的消息
  const visibleMessages = useMemo(() => {
    if (messages.length <= LOAD_MORE_THRESHOLD || showAllMessages) {
      return messages;
    }
    return messages.slice(-MAX_VISIBLE_MESSAGES);
  }, [messages, showAllMessages]);

  const hasHiddenMessages = messages.length > LOAD_MORE_THRESHOLD && !showAllMessages;

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  useEffect(() => {
    return () => { abortRef.current = true; };
  }, []);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || sending || streaming) return;

    const userContent = input.trim();
    const userMsg: QAMessage = {
      id: Date.now(),
      role: "user",
      content: userContent,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);

    const aiMsgId = Date.now() + 1;
    const aiMsg: QAMessage = {
      id: aiMsgId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, aiMsg]);

    setSending(false);
    setStreaming(true);

    await streamRequest("/student/qa/chat/stream", {
      method: "POST",
      body: {
        message: userContent,
        session_id: sessionId || undefined,
        subject_id: getSubjectId(subject),
      },
      onMessage: (data) => {
        if (abortRef.current) return;
        try {
          const event = JSON.parse(data);
          if (event.type === "chunk") {
            setMessages((prev) =>
              prev.map((m) => m.id === aiMsgId
                ? { ...m, content: m.content + event.content }
                : m
              )
            );
          } else if (event.type === "knowledge_points") {
            setMessages((prev) =>
              prev.map((m) => m.id === aiMsgId
                ? { ...m, knowledge_points: event.data }
                : m
              )
            );
          } else if (event.type === "strategy") {
            setMessages((prev) =>
              prev.map((m) => m.id === aiMsgId
                ? { ...m, tutoring_strategy: event.data }
                : m
              )
            );
          } else if (
            (event.type === "session_created" || event.type === "session_id") &&
            (event.session_id || event.data)
          ) {
            setSessionId(event.session_id ?? event.data);
          } else if (event.type === "session_created" && event.session_id) {
            setSessionId(event.session_id);
          } else if (event.type === "session_id" && event.data) {
            setSessionId(event.data);
          }
        } catch { /* ignore non-JSON lines */ }
      },
      onDone: () => {
        if (!abortRef.current) setStreaming(false);
      },
      onError: () => {
        if (!abortRef.current) {
          setStreaming(false);
          toast("回复生成失败，请重试", "error");
        }
      },
    });
  }, [input, sending, streaming, sessionId, subject, toast]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function formatKnowledgePoints(kps: QAMessage["knowledge_points"]): string {
    if (!kps || kps.length === 0) return "";
    return kps.map((kp) => typeof kp === "string" ? kp : kp.name).join("、");
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
            {qaHistory.length > 0 ? qaHistory.map((s) => (
              <button
                key={s.id}
                className="w-full text-left p-3 rounded-lg hover:bg-gray-50 mb-1 transition-colors"
                onClick={() => setShowHistory(false)}
              >
                <p className="text-sm font-medium">会话 #{s.id}</p>
                <p className="text-xs text-text-tertiary">{s.message_count}条消息 · {new Date(s.created_at).toLocaleDateString("zh-CN")}</p>
              </button>
            )) : (
              <p className="text-sm text-text-tertiary">暂无历史会话</p>
            )}
          </div>
        </>
      )}

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4 max-w-3xl mx-auto w-full">
        <div
          className="space-y-4"
          role="log"
          aria-live="polite"
          aria-label="聊天记录"
        >
          {/* 加载更多历史消息按钮 */}
          {hasHiddenMessages && (
            <div className="text-center py-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAllMessages(true)}
              >
                加载更多历史消息（{messages.length - MAX_VISIBLE_MESSAGES} 条）
              </Button>
            </div>
          )}
          {visibleMessages.map((msg) => (
            <div key={msg.id} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
              <div className={cn(
                "max-w-[85%] md:max-w-[75%] rounded-2xl px-4 py-3",
                msg.role === "user" ? "bg-primary text-white" : "bg-card border border-border"
              )}>
                {/* Strategy tag */}
                {msg.tutoring_strategy && (
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-text-secondary">AI 助教</span>
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
                  streaming && msg === visibleMessages[visibleMessages.length - 1] && msg.role === "assistant" && "streaming-cursor"
                )}>
                  {msg.content}
                </div>

                {/* Knowledge points */}
                {msg.knowledge_points && msg.knowledge_points.length > 0 && msg.content.length > 0 && !streaming && (
                  <div className="mt-3 pt-3 border-t border-border-light">
                    <p className="text-xs text-text-tertiary">关联知识点：{formatKnowledgePoints(msg.knowledge_points)}</p>
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

        {/* Next Step Guide */}
        {messages.length > 4 && !streaming && !sending && (
          <div className="mt-4 p-3 bg-card border border-border rounded-xl">
            <p className="text-sm text-text-secondary mb-2">下一步</p>
            <div className="flex gap-2 flex-wrap">
              <Button variant="outline" size="sm">巩固练习</Button>
              <Button variant="outline" size="sm">类似题</Button>
              <Button variant="outline" size="sm" onClick={() => document.querySelector("textarea")?.focus()}>继续追问</Button>
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
            aria-label="输入问题"
            aria-describedby={inputDescId}
            className="flex-1 px-3 py-2.5 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none max-h-32"
            style={{ minHeight: "42px" }}
          />

          <button
            onClick={sendMessage}
            disabled={!input.trim() || sending || streaming}
            aria-disabled={!input.trim() || sending || streaming}
            className={cn(
              "p-2.5 rounded-lg transition-colors shrink-0",
              input.trim() && !sending && !streaming ? "bg-primary text-white hover:bg-primary-hover" : "bg-gray-100 text-text-tertiary"
            )}
            aria-label="发送"
          >
            ➤
          </button>
        </div>
        <p id={inputDescId} className="text-xs text-text-tertiary text-center mt-1.5 max-w-3xl mx-auto">Enter 发送，Shift+Enter 换行</p>
      </div>
    </div>
  );
}
