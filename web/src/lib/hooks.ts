import useSWR from "swr";
import { api } from "./api";
import type {
  DailyPlan,
  StudyUpload,
  QASession,
  ErrorBookItem,
  ErrorSummary,
  KnowledgeStatusResponse,
  WeeklyReport,
  ParentWeeklyReport,
  SystemMetrics,
  CorrectionItem,
  CostTrendData,
  FallbackStatsData,
  ErrorStatsData,
  LatencyStatsData,
  CorrectionDetail,
  PendingCountByType,
} from "@/types/api";

const fetcher = <T>(path: string) => api.get<T>(path);

// === Student ===

export function useDailyPlan() {
  return useSWR<DailyPlan | null>("/student/plan/today", fetcher);
}

export function useRecentUploads(page = 1, pageSize = 3) {
  return useSWR<{ items: StudyUpload[]; total: number }>(
    `/student/material/list?page=${page}&page_size=${pageSize}`,
    fetcher
  );
}

export function useUploadOcrStatus(uploadId: number | null) {
  return useSWR(
    uploadId ? `/student/material/${uploadId}/ocr-status` : null,
    fetcher,
    { refreshInterval: 3000 }
  );
}

export function useQAHistory(page = 1, pageSize = 10) {
  return useSWR<{ items: QASession[]; total: number }>(
    `/student/qa/history?page=${page}&page_size=${pageSize}`,
    fetcher
  );
}

export function useSessionDetail(sessionId: number | null) {
  return useSWR(
    sessionId ? `/student/qa/sessions/${sessionId}` : null,
    fetcher
  );
}

export function useErrorList(params: {
  subject_id?: number;
  is_recalled?: boolean;
  page?: number;
  page_size?: number;
}) {
  const query = new URLSearchParams();
  if (params.subject_id) query.set("subject_id", String(params.subject_id));
  if (params.is_recalled !== undefined) query.set("is_recalled", String(params.is_recalled));
  query.set("page", String(params.page || 1));
  query.set("page_size", String(params.page_size || 20));
  return useSWR<{ items: ErrorBookItem[]; total: number }>(
    `/student/errors?${query}`,
    fetcher
  );
}

export function useErrorSummary() {
  return useSWR<ErrorSummary>("/student/errors/summary", fetcher);
}

export function useKnowledgeStatus() {
  return useSWR<KnowledgeStatusResponse>("/student/knowledge/status", fetcher);
}

export function useWeeklyReport(week?: string | null) {
  const path = week === null
    ? null
    : week
      ? `/student/report/weekly?week=${week}`
      : "/student/report/weekly";
  return useSWR<WeeklyReport>(path, fetcher);
}

export function useWeeklyReportSummary() {
  return useSWR("/student/report/weekly/summary", fetcher);
}

// === Parent ===

export function useParentWeeklyReport(week?: string | null) {
  const path = week === null
    ? null
    : week
      ? `/parent/report/weekly?week=${week}`
      : "/parent/report/weekly";
  return useSWR<ParentWeeklyReport>(path, fetcher);
}

export function useParentRisk() {
  return useSWR("/parent/profile/risk", fetcher);
}

export function useParentTrend() {
  return useSWR("/parent/profile/trend", fetcher);
}

// === Admin ===

export function useAdminMetrics() {
  return useSWR<SystemMetrics>("/admin/metrics/today", fetcher);
}

export function useAdminHealth() {
  return useSWR("/admin/metrics/health", fetcher);
}

export function useModelCalls() {
  return useSWR("/admin/metrics/model-calls", fetcher);
}

export function usePendingCorrections(page = 1) {
  return useSWR<{ items: CorrectionItem[]; total: number }>(
    `/admin/corrections/pending?page=${page}&page_size=20`,
    fetcher
  );
}

export function useSystemMode() {
  return useSWR<{ mode: string }>("/admin/system/mode", fetcher);
}

// Phase 5: Admin metrics hooks

export function useCostTrend(period = "today") {
  return useSWR<CostTrendData>(
    `/admin/metrics/costs?period=${period}`,
    fetcher
  );
}

export function useFallbackStats(period = "today") {
  return useSWR<FallbackStatsData>(
    `/admin/metrics/fallbacks?period=${period}`,
    fetcher
  );
}

export function useErrorStats(period = "today") {
  return useSWR<ErrorStatsData>(
    `/admin/metrics/errors?period=${period}`,
    fetcher
  );
}

export function useLatencyStats(period = "today") {
  return useSWR<LatencyStatsData>(
    `/admin/metrics/latency?period=${period}`,
    fetcher
  );
}

export function useCorrectionDetail(id: number | null) {
  return useSWR<CorrectionDetail>(
    id ? `/admin/corrections/${id}` : null,
    fetcher
  );
}

export function useCorrectionLogs(page = 1, pageSize = 20) {
  return useSWR<{ items: CorrectionItem[]; total: number }>(
    `/admin/corrections/logs?page=${page}&page_size=${pageSize}`,
    fetcher
  );
}

export function usePendingCountByType() {
  return useSWR<PendingCountByType>(
    "/admin/corrections/pending/count",
    fetcher
  );
}
