export function cn(...classes: (string | boolean | undefined | null)[]) {
  return classes.filter(Boolean).join(" ");
}

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

export function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "";
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
}

export function formatRelativeTime(dateStr: string): string {
  const now = new Date();
  const d = new Date(dateStr);
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return `今天 ${formatTime(dateStr)}`;
  if (diffDays === 1) return `昨天 ${formatTime(dateStr)}`;
  return `${formatDate(dateStr)}`;
}

export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes}min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}min` : `${h}h`;
}

export function getWeekday(dateStr: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "";
  const days = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
  return days[d.getDay()];
}

export const uploadTypeLabels: Record<string, string> = {
  note: "笔记", homework: "作业", test: "练习卷", handout: "讲义", score: "成绩",
};

export const taskTypeLabels: Record<string, { label: string; icon: string }> = {
  lecture: { label: "知识点讲解", icon: "📚" },
  practice: { label: "巩固练习", icon: "✏️" },
  error_review: { label: "错题回顾", icon: "📕" },
  consolidation: { label: "同类题巩固", icon: "🔄" },
};

export const modeLabels: Record<string, string> = {
  workday_follow: "工作日跟学",
  weekend_review: "周末复习",
  exam_sprint: "考试冲刺",
};

export const entryReasonLabels: Record<string, string> = {
  wrong: "做错", not_know: "不会", repeated_wrong: "反复错",
};

export const errorTypeLabels: Record<string, string> = {
  calc_error: "计算错误",
  concept_unclear: "概念不清",
  careless: "粗心",
  unknown: "未知",
  "计算错误": "计算错误",
  "概念不清": "概念不清",
  "粗心": "粗心",
  "不会": "不会",
};

export const riskLevelLabels: Record<string, { label: string; color: string }> = {
  stable: { label: "稳定", color: "text-success" },
  low_risk: { label: "轻度风险", color: "text-warning" },
  medium_risk: { label: "中度风险", color: "text-orange-500" },
  high_risk: { label: "高风险", color: "text-error" },
};

export const trendLabels: Record<string, { label: string; icon: string }> = {
  improving: { label: "上升", icon: "↑" },
  stable: { label: "稳定", icon: "→" },
  declining: { label: "下降", icon: "↓" },
};
