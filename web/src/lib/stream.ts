import { getToken } from "./api";
import { env } from "./env";

export interface StreamOptions {
  onMessage?: (data: string) => void;
  onError?: (error: Error) => void;
  onDone?: () => void;
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

/**
 * Utility for handling SSE (Server-Sent Events) via fetch.
 * This is preferred over EventSource when we need to pass Authorization headers or use POST.
 */
export async function streamRequest(path: string, options: StreamOptions = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    Accept: "text/event-stream",
    ...options.headers,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  try {
    const response = await fetch(`${env.NEXT_PUBLIC_API_BASE}${path}`, {
      method: options.method || "GET",
      headers,
      body: options.body instanceof FormData ? options.body : (options.body ? JSON.stringify(options.body) : undefined),
    });

    if (!response.ok) {
      throw new Error(`HTTP Error: ${response.status}`);
    }

    if (!response.body) {
      throw new Error("Response body is empty.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");

      // Keep the last incomplete line in the buffer
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") {
            if (options.onDone) options.onDone();
            return;
          }
          if (options.onMessage) options.onMessage(data);
        }
      }
    }

    // Process any remaining buffer
    if (buffer.startsWith("data: ")) {
      const data = buffer.slice(6);
      if (data !== "[DONE]" && options.onMessage) {
        options.onMessage(data);
      }
    }

    if (options.onDone) options.onDone();

  } catch (error) {
    if (options.onError) {
      options.onError(error instanceof Error ? error : new Error(String(error)));
    } else {
      console.error("Stream request failed:", error);
    }
  }
}
