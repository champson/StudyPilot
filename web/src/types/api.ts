// ============================================
// API Types - aligned with backend schemas
// ============================================

// --- Global ---
export interface SuccessResponse<T> {
  data: T;
  meta?: { request_id?: string; server_time?: string };
}

export interface PaginatedResponse<T> {
  data: {
    items: T[];
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    detail: Record<string, unknown>;
  };
}

// --- Auth ---
export interface LoginRequest {
  token: string;
  role: "student" | "parent";
}

export interface AdminLoginRequest {
  username: string;
  password: string;
}

export interface AuthUser {
  id: number;
  role: "student" | "parent" | "admin";
  nickname: string;
  student_id: number | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

// --- Student Profile ---
export type Grade = "高一" | "高二" | "高三";
export type Subject = "语文" | "数学" | "英语" | "物理" | "化学" | "地理" | "政治" | "生物" | "历史";
export type ExamType = "周测" | "月考" | "期中" | "期末";

export interface StudentProfile {
  id: number;
  user_id: number;
  grade: Grade;
  textbook_version: string;
  class_rank?: number;
  grade_rank?: number;
  class_total?: number;
  grade_total?: number;
  subject_combination: Subject[];
  onboarding_completed: boolean;
  created_at: string;
}

export interface OnboardingData {
  grade: Grade;
  textbook_version: string;
  class_rank?: number;
  grade_rank?: number;
  class_total?: number;
  grade_total?: number;
  subject_combination: Subject[];
  exam_schedules?: ExamSchedule[];
}

export interface ExamSchedule {
  id?: number;
  exam_type: ExamType;
  exam_date: string;
  subjects: Subject[];
}

// --- Daily Plan (matches DailyPlanOut / PlanTaskOut) ---
export type LearningMode = "workday_follow" | "weekend_review" | "exam_sprint";
export type PlanSource = "upload_corrected" | "history_inferred" | "manual_adjusted" | "generic_fallback";
export type TaskType = "lecture" | "practice" | "error_review" | "consolidation";
export type TaskStatus = "pending" | "entered" | "executed" | "completed";

export interface DailyPlan {
  id: number;
  student_id: number;
  plan_date: string;
  learning_mode: LearningMode;
  system_recommended_mode?: string;
  available_minutes: number;
  source: PlanSource;
  is_history_inferred: boolean;
  recommended_subjects: Record<string, unknown>;
  plan_content: Record<string, unknown>;
  status: string;
  created_at: string;
  tasks: PlanTask[];
}

export interface PlanTask {
  id: number;
  plan_id: number;
  subject_id: number;
  task_type: TaskType;
  task_content: { title?: string; description?: string; reasons?: string[] };
  sequence: number;
  estimated_minutes?: number;
  status: TaskStatus;
  started_at?: string;
  completed_at?: string;
  duration_minutes?: number;
}

// --- Upload (matches UploadOut) ---
export type UploadType = "note" | "homework" | "test" | "handout" | "score";
export type OcrStatus = "pending" | "processing" | "completed" | "failed";

export interface StudyUpload {
  id: number;
  student_id: number;
  upload_type: UploadType;
  subject_id: number | null;
  file_hash: string;
  original_url: string;
  thumbnail_url?: string;
  ocr_status: OcrStatus;
  ocr_result?: Record<string, unknown>;
  ocr_error?: string;
  created_at: string;
}

// --- QA (matches QaSessionListItem / QaMessageOut) ---
export interface QASession {
  id: number;
  session_date: string;
  subject_id: number | null;
  status: string;
  created_at: string;
  message_count: number;
}

export interface QASessionDetail {
  id: number;
  student_id: number;
  session_date: string;
  task_id: number | null;
  subject_id: number | null;
  status: string;
  structured_summary: Record<string, unknown> | null;
  created_at: string;
  closed_at: string | null;
  messages: QAMessage[];
}

export interface QAMessage {
  id: number;
  session_id?: number;
  role: "user" | "assistant";
  content: string;
  attachments?: string[];
  intent?: string;
  tutoring_strategy?: "hint" | "step_by_step" | "formula" | "full_solution";
  knowledge_points?: Array<{ id?: number; name: string } | string>;
  created_at: string;
}

export interface ChatResponse {
  session_id: number;
  user_message: QAMessage;
  assistant_message: QAMessage;
}

// --- Error Book (matches ErrorBookOut / ErrorSummaryOut) ---
export type ErrorType = "计算错误" | "概念不清" | "粗心" | "不会";
export type EntryReason = "wrong" | "not_know" | "repeated_wrong";

export interface ErrorBookItem {
  id: number;
  student_id: number;
  subject_id: number;
  question_content: { text?: string; [key: string]: unknown };
  question_image_url?: string;
  knowledge_points: Array<{ id?: number; name: string }>;
  error_type?: string;
  entry_reason: EntryReason;
  content_hash?: string;
  is_explained: boolean;
  is_recalled: boolean;
  last_recall_at?: string;
  last_recall_result?: string;
  recall_count: number;
  source_upload_id?: number;
  created_at: string;
}

export interface ErrorSubjectSummary {
  subject_id: number;
  subject_name: string;
  count: number;
  unrecalled: number;
}

export interface ErrorSummary {
  total: number;
  unrecalled: number;
  by_subject: ErrorSubjectSummary[];
  by_error_type: Record<string, number>;
}

// --- Weekly Report (matches WeeklyReportOut) ---
export interface SubjectTrend {
  subject_name: string;
  risk_level: string;
  trend: "improving" | "stable" | "declining";
}

export interface HighRiskKnowledgePoint {
  name: string;
  subject_name: string;
  status: string;
}

export interface RepeatedErrorPoint {
  name: string;
  error_count: number;
}

export interface WeeklyReport {
  id: number;
  student_id: number;
  report_week: string;
  usage_days?: number;
  total_minutes?: number;
  task_completion_rate?: number;
  subject_trends: SubjectTrend[];
  high_risk_knowledge_points: HighRiskKnowledgePoint[];
  repeated_error_points: RepeatedErrorPoint[];
  next_stage_suggestions: string[];
  class_rank?: number;
  grade_rank?: number;
  share_token?: string;
  created_at: string;
}

// --- Parent Report (matches ParentWeeklyReportOut) ---
export interface ParentSubjectRisk {
  subject_id: number;
  subject_name: string;
  risk_level: string;
  effective_week: string;
}

export interface ParentWeeklyReport {
  report_week: string;
  student_name?: string;
  usage_days?: number;
  total_minutes?: number;
  task_completion_rate?: number;
  subject_risks: ParentSubjectRisk[];
  trend_description?: string;
  action_suggestions: string[];
  class_rank?: number;
  grade_rank?: number;
  share_token?: string;
  created_at: string;
}

// --- Share (matches ShareContentOut) ---
export interface SubjectRiskOverview {
  subject_name: string;
  risk_level: string;
}

export interface ShareReport {
  student_name?: string;
  report_week: string;
  usage_days?: number;
  total_minutes?: number;
  trend_overview?: string;
  subject_risk_overview: SubjectRiskOverview[];
  next_stage_suggestions_summary?: string;
  expires_at?: string;
}

// --- Admin ---
// Matches CorrectionOut
export interface CorrectionItem {
  id: number;
  target_type: string;
  target_id: number;
  original_content: Record<string, unknown> | null;
  corrected_content: Record<string, unknown>;
  correction_reason: string | null;
  corrected_by: number;
  status: string;
  created_at: string;
}

// Matches MetricsTodayOut
export interface SystemMetrics {
  active_students: number;
  plans_generated: number;
  uploads: number;
  qa_sessions: number;
}

// Matches HealthOut
export interface HealthStatus {
  database: string;
  redis: string;
  celery: string;
}

// Matches ModelCallsOut
export interface ModelCallsData {
  total: number;
  by_agent: Array<{ agent?: string; count?: number; [key: string]: unknown }>;
  by_provider: Array<{ provider?: string; count?: number; [key: string]: unknown }>;
}
