"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/admin/dashboard", label: "仪表盘", icon: "📊" },
  { href: "/admin/corrections", label: "人工纠偏", icon: "🔧" },
  { href: "/admin/metrics", label: "监控统计", icon: "📈" },
];

export function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [authorized] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("user_role") === "admin";
  });

  useEffect(() => {
    if (!authorized) {
      router.replace("/login");
    }
  }, [authorized, router]);

  if (!authorized) return null;

  return (
    <div className="min-h-screen bg-bg">
      <header className="sticky top-0 z-50 bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 md:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-text-primary rounded-lg flex items-center justify-center text-white font-bold text-xs">管</div>
            <span className="font-semibold text-text-primary">管理后台</span>
          </div>
          <button
            onClick={() => { localStorage.removeItem("access_token"); localStorage.removeItem("user_role"); router.push("/login"); }}
            className="text-sm text-text-secondary hover:text-error transition-colors"
          >
            退出
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto flex">
        <nav className="hidden md:block w-52 shrink-0 border-r border-border bg-card min-h-[calc(100vh-56px)] p-3">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm mb-1 transition-colors",
                pathname === item.href
                  ? "bg-primary-light text-primary font-medium"
                  : "text-text-secondary hover:bg-gray-50"
              )}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>

        <main className="flex-1 min-w-0">
          {/* Mobile nav */}
          <div className="md:hidden flex border-b border-border bg-card overflow-x-auto">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-1 px-4 py-3 text-sm whitespace-nowrap border-b-2 transition-colors",
                  pathname === item.href
                    ? "border-primary text-primary font-medium"
                    : "border-transparent text-text-secondary"
                )}
              >
                <span>{item.icon}</span>
                {item.label}
              </Link>
            ))}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
