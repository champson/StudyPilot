"use client";

import { useState, useCallback, createContext, useContext } from "react";
import { cn } from "@/lib/utils";

interface Toast {
  id: number;
  message: string;
  type: "success" | "error" | "warning" | "info";
}

interface ToastContextType {
  toast: (message: string, type?: Toast["type"]) => void;
}

const ToastContext = createContext<ToastContextType>({ toast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

let nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, type: Toast["type"] = "info") => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  }, []);

  const typeStyles = {
    success: "bg-success text-white",
    error: "bg-error text-white",
    warning: "bg-warning text-white",
    info: "bg-text-primary text-white",
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed top-4 right-4 z-[1000] flex flex-col gap-2" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn("px-4 py-3 rounded-lg shadow-lg text-sm animate-[slideIn_0.2s_ease-out]", typeStyles[t.type])}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
