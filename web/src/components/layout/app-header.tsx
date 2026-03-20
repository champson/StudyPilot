"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { clearAuth } from "@/lib/auth";

interface AppHeaderProps {
  showMode?: boolean;
  currentMode?: string;
  onModeChange?: (mode: string) => void;
  userName?: string;
}

export function AppHeader({ showMode, currentMode, onModeChange, userName = "小明" }: AppHeaderProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const router = useRouter();

  const modes = [
    { value: "workday_follow", label: "工作日跟学" },
    { value: "weekend_review", label: "周末复习" },
  ];

  return (
    <header className="sticky top-0 z-50 bg-card border-b border-border">
      <div className="max-w-7xl mx-auto px-4 md:px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-white font-bold text-sm">AI</div>
            <span className="font-semibold text-text-primary hidden sm:block">AI 伴学教练</span>
          </Link>
          {showMode && currentMode && (
            <div className="relative ml-4">
              <button
                onClick={() => setShowDropdown(!showDropdown)}
                className="flex items-center gap-1 px-3 py-1.5 text-sm bg-primary-light text-primary rounded-lg hover:bg-blue-100 transition-colors"
              >
                {modes.find((m) => m.value === currentMode)?.label}
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
              </button>
              {showDropdown && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setShowDropdown(false)} />
                  <div className="absolute top-full mt-1 left-0 bg-card border border-border rounded-lg shadow-lg z-20 py-1 min-w-[140px]">
                    {modes.map((m) => (
                      <button
                        key={m.value}
                        onClick={() => { onModeChange?.(m.value); setShowDropdown(false); }}
                        className={cn(
                          "w-full text-left px-4 py-2 text-sm hover:bg-gray-50 transition-colors",
                          m.value === currentMode && "text-primary font-medium"
                        )}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center text-sm">
              {userName.charAt(0)}
            </div>
            <span className="text-sm text-text-primary hidden sm:block">{userName}</span>
          </button>
          {showUserMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowUserMenu(false)} />
              <div className="absolute top-full mt-1 right-0 bg-card border border-border rounded-lg shadow-lg z-20 py-1 min-w-[120px]">
                <button onClick={() => { router.push("/report/weekly"); setShowUserMenu(false); }} className="w-full text-left px-4 py-2 text-sm hover:bg-gray-50">周报</button>
                <hr className="my-1 border-border-light" />
                <button onClick={() => { clearAuth(); router.push("/login"); setShowUserMenu(false); }} className="w-full text-left px-4 py-2 text-sm text-error hover:bg-gray-50">退出登录</button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export function PageHeader({ title, backHref, rightContent }: { title: string; backHref?: string; rightContent?: React.ReactNode }) {
  const router = useRouter();
  return (
    <header className="sticky top-0 z-50 bg-card border-b border-border">
      <div className="max-w-7xl mx-auto px-4 md:px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {backHref && (
            <button onClick={() => router.push(backHref)} className="p-1 -ml-1 hover:bg-gray-100 rounded-lg transition-colors" aria-label="返回">
              <svg className="w-5 h-5 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            </button>
          )}
          <h1 className="text-lg font-semibold text-text-primary">{title}</h1>
        </div>
        {rightContent && <div className="flex items-center gap-2">{rightContent}</div>}
      </div>
    </header>
  );
}
