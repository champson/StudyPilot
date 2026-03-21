"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useCorrectionLogs } from "@/lib/hooks";
import type { CorrectionItem } from "@/types/api";

export function CorrectionLogList() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useCorrectionLogs(page, 10);
  const [accumulated, setAccumulated] = useState<CorrectionItem[]>([]);
  const seenIds = useRef(new Set<number>());

  const appendItems = useCallback((items: CorrectionItem[]) => {
    const newItems = items.filter((i) => !seenIds.current.has(i.id));
    if (newItems.length > 0) {
      for (const i of newItems) seenIds.current.add(i.id);
      setAccumulated((prev) => [...prev, ...newItems]);
    }
  }, []);

  useEffect(() => {
    if (data?.items) {
      appendItems(data.items);
    }
  }, [data, appendItems]);

  const total = data?.total || 0;
  const hasMore = accumulated.length < total;

  if (isLoading && accumulated.length === 0) {
    return <p className="text-sm text-text-tertiary text-center py-4">加载中...</p>;
  }

  if (accumulated.length === 0) {
    return <p className="text-sm text-text-tertiary text-center py-4">暂无修正记录</p>;
  }

  return (
    <div className="space-y-2">
      {accumulated.map((item) => (
        <div key={item.id} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
          <div className="flex items-center gap-2">
            <Badge variant={item.target_type === "ocr" ? "warning" : item.target_type === "knowledge" ? "error" : "primary"}>
              {item.target_type.toUpperCase()}
            </Badge>
            <span className="text-sm text-text-secondary">#{item.id}</span>
            <span className="text-xs text-text-tertiary">{new Date(item.created_at).toLocaleString("zh-CN")}</span>
          </div>
          <Badge variant="success">已处理</Badge>
        </div>
      ))}
      {hasMore && (
        <div className="text-center pt-2">
          <Button variant="outline" size="sm" onClick={() => setPage(page + 1)} disabled={isLoading}>
            {isLoading ? "加载中..." : "加载更多"}
          </Button>
        </div>
      )}
    </div>
  );
}
