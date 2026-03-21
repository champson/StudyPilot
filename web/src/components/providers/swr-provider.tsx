"use client";

import { SWRConfig } from "swr";

const swrConfig = {
  dedupingInterval: 60000, // 60秒内相同请求去重
  focusThrottleInterval: 60000, // 窗口获焦时60秒内不重复请求
  revalidateOnFocus: true,
  shouldRetryOnError: true,
  errorRetryCount: 3,
  onError: (error: unknown) => {
    // 401 错误统一跳转登录
    const err = error as { status?: number };
    if (err?.status === 401) {
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
  },
};

export function SWRProvider({ children }: { children: React.ReactNode }) {
  return <SWRConfig value={swrConfig}>{children}</SWRConfig>;
}
