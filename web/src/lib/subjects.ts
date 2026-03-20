// Subject ID → display info mapping
// In Phase 3 this will come from the API; for now hardcoded to match seed data.

import type { Subject } from "@/types/api";

export interface SubjectInfo {
  name: Subject;
  icon: string;
}

const SUBJECT_MAP: Record<number, SubjectInfo> = {
  1: { name: "数学", icon: "📐" },
  2: { name: "语文", icon: "📝" },
  3: { name: "英语", icon: "📖" },
  4: { name: "物理", icon: "⚡" },
  5: { name: "化学", icon: "🧪" },
  6: { name: "地理", icon: "🌍" },
  7: { name: "政治", icon: "📜" },
  8: { name: "生物", icon: "🧬" },
  9: { name: "历史", icon: "📚" },
};

export function getSubject(id: number): SubjectInfo {
  return SUBJECT_MAP[id] ?? { name: "未知" as Subject, icon: "📄" };
}

const NAME_TO_ID: Record<string, number> = Object.fromEntries(
  Object.entries(SUBJECT_MAP).map(([id, info]) => [info.name, Number(id)])
);

export function getSubjectId(name: string): number {
  return NAME_TO_ID[name] ?? 0;
}
