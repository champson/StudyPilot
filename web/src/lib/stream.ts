import { getToken, AUTH_STORAGE_KEYS } from "./api";
import { env } from "./env";

/** Default timeout for stream requests (longer than regular requests) */
const DEFAULT_STREAM_TIMEOUT = 60000; // 60 seconds

export interface StreamOptions {
  onMessage?: (data: string) => void;
  onError?: (error: Error) => void;
  onDone?: () => void;
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  timeout?: number;
}

/**
 * Utility for handling SSE (Server-Sent Events) via fetch.
 * This is preferred over EventSource when we need to pass Authorization headers or use POST.
 */
export async function streamRequest(path: string, options: StreamOptions = {}) {
  const { timeout = DEFAULT_STREAM_TIMEOUT, ...restOptions } = options;
  const token = getToken();
  const headers: Record<string, string> = {
    Accept: "text/event-stream",
    ...restOptions.headers,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (restOptions.body && !(restOptions.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  // Set up AbortController for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, timeout);

  try {
    const response = await fetch(`${env.NEXT_PUBLIC_API_BASE}${path}`, {
      method: restOptions.method || "GET",
      headers,
      body: restOptions.body instanceof FormData 
        ? restOptions.body 
        : (restOptions.body ? JSON.stringify(restOptions.body) : undefined),
      signal: controller.signal,
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        if (typeof window !== "undefined") {
          for (const key of AUTH_STORAGE_KEYS) localStorage.removeItem(key);
          document.cookie = "access_token=; path=/; max-age=0";
          window.location.href = "/login";
        }
      }
      throw new Error(`HTTP Error: ${response.status}`);
    }

    if (!response.body) {
      throw new Error("Response body is empty.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    // Clear initial timeout since connection is established
    // Set up a new timeout for reading (reset on each chunk)
    let readTimeoutId: ReturnType<typeof setTimeout> | null = null;
    let timedOut = false;
    const resetReadTimeout = () => {
      if (readTimeoutId) clearTimeout(readTimeoutId);
      readTimeoutId = setTimeout(() => {
        timedOut = true;
        reader.cancel();
      }, timeout);
    };

    clearTimeout(timeoutId); // Clear the initial connection timeout
    resetReadTimeout(); // Start read timeout

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        resetReadTimeout(); // Reset timeout on each chunk

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");

        // Keep the last incomplete line in the buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") {
              if (readTimeoutId) clearTimeout(readTimeoutId);
              if (options.onDone) options.onDone();
              return;
            }
            if (options.onMessage) options.onMessage(data);
          }
        }
      }

      if (readTimeoutId) clearTimeout(readTimeoutId);

      // Distinguish timeout-induced cancellation from normal end-of-stream
      if (timedOut) {
        if (options.onError) options.onError(new Error("流式请求超时"));
        return;
      }

      // Process any remaining buffer
      if (buffer.startsWith("data: ")) {
        const data = buffer.slice(6);
        if (data !== "[DONE]" && options.onMessage) {
          options.onMessage(data);
        }
      }

      if (options.onDone) options.onDone();
    } finally {
      if (readTimeoutId) clearTimeout(readTimeoutId);
    }

  } catch (error) {
    clearTimeout(timeoutId);
    
    // Handle abort/timeout
    if (error instanceof Error && error.name === 'AbortError') {
      if (options.onError) {
        options.onError(new Error('请求超时'));
      }
      return;
    }
    
    if (options.onError) {
      options.onError(error instanceof Error ? error : new Error(String(error)));
    } else {
      console.error("Stream request failed:", error);
    }
  }
}
