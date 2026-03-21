"use client";

import { useState, useMemo } from "react";
import { cn } from "@/lib/utils";

interface WeekOption {
  value: string; // "YYYY-WNN"
  label: string; // "第N周 M.D-M.D"
}

/** Standard ISO 8601 week number via nearest-Thursday algorithm */
function isoWeek(d: Date): { year: number; week: number } {
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  // Set to nearest Thursday: current date + 4 - current day number (Mon=1..Sun=7)
  const dayNum = target.getDay() || 7;
  target.setDate(target.getDate() + 4 - dayNum);
  const jan1 = new Date(target.getFullYear(), 0, 1);
  const weekNum = Math.ceil(((target.getTime() - jan1.getTime()) / 86400000 + 1) / 7);
  return { year: target.getFullYear(), week: weekNum };
}

function getRecentWeeks(count: number): WeekOption[] {
  const weeks: WeekOption[] = [];
  const now = new Date();
  for (let i = 0; i < count; i++) {
    const d = new Date(now);
    d.setDate(d.getDate() - i * 7);
    const iso = isoWeek(d);
    const value = `${iso.year}-W${String(iso.week).padStart(2, "0")}`;
    // Week start (Monday)
    const weekday = d.getDay() || 7;
    const monday = new Date(d);
    monday.setDate(monday.getDate() - (weekday - 1));
    const sunday = new Date(monday);
    sunday.setDate(sunday.getDate() + 6);
    const label = `第${iso.week}周 ${monday.getMonth() + 1}.${monday.getDate()}-${sunday.getMonth() + 1}.${sunday.getDate()}`;
    if (!weeks.some((w) => w.value === value)) {
      weeks.push({ value, label });
    }
  }
  return weeks;
}

interface WeekSelectorProps {
  value?: string;
  onChange: (week: string) => void;
  /** The list of recent weeks; exposed so callers can read the default */
  weeks?: WeekOption[];
}

export function useRecentWeeks() {
  return useMemo(() => getRecentWeeks(8), []);
}

export function WeekSelector({ value, onChange }: WeekSelectorProps) {
  const [open, setOpen] = useState(false);
  const weeks = useRecentWeeks();
  const selected = weeks.find((w) => w.value === value) || weeks[0];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-card border border-border rounded-lg text-sm hover:bg-gray-50 transition-colors"
      >
        <span>{selected?.label || "选择周期"}</span>
        <svg className={cn("w-4 h-4 transition-transform", open && "rotate-180")} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 bg-card border border-border rounded-lg shadow-lg py-1 min-w-[180px]">
          {weeks.map((w) => (
            <button
              key={w.value}
              onClick={() => {
                onChange(w.value);
                setOpen(false);
              }}
              className={cn(
                "w-full text-left px-3 py-2 text-sm hover:bg-gray-50 transition-colors",
                w.value === (value || weeks[0]?.value) && "text-primary font-medium bg-primary-light/50"
              )}
            >
              {w.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
