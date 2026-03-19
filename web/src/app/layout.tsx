import type { Metadata } from "next";
import "./globals.css";
import { ToastProvider } from "@/components/ui/toast";

export const metadata: Metadata = {
  title: "AI 伴学教练 - 高考学习伴侣",
  description: "面向上海高中生的 AI 伴学教练，个性化学习计划与实时答疑",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
