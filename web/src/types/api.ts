// ============================================
// API Types - based on docs/api-contract.md
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

// --- Daily Plan ---
export type LearningMode = "workday_follow" | "weekend_review" | "exam_sprint";
export type PlanSource = "upload_corrected" | "history_inferred" | "manual_adjusted" | "generic_fallback";
export type TaskType = "lecture" | "practice" | "error_review" | "consolidation";
export type TaskStatus = "pending" | "entered" | "executed" | "completed";

export interface DailyPlan {
  id: number;
  plan_date: string;
  learning_mode: LearningMode;
  available_minutes: number;
  source: PlanSource;
  status: "generated" | "in_progress" | "completed";
  recommended_subjects: RecommendedSubject[];
  tasks: PlanTask[];
  completed_tasks: number;
  total_tasks: number;
}

export interface RecommendedSubject {
  name: Subject;
  reasons: string[];
}

export interface PlanTask {
  id: number;
  sequence: number;
  subject: { name: Subject; icon: string };
  task_type: TaskType;
  title: string;
  description: string;
  reasons: string[];
  estimated_minutes: number;
  status: TaskStatus;
  completed_at?: string;
  duration_minutes?: number;
}

// --- Upload ---
export type UploadType = "note" | "homework" | "test" | "handout" | "score";
export type OcrStatus = "pending" | "processing" | "completed" | "failed";

export interface StudyUpload {
  id: number;
  upload_type: UploadType;
  subject?: Subject;
  note?: string;
  file_urls: string[];
  ocr_status: OcrStatus;
  created_at: string;
}

// --- QA ---
export interface QASession {
  id: number;
  subject?: Subject;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface QAMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  attachments?: string[];
  tutoring_strategy?: "hint" | "step_by_step" | "formula" | "full_solution";
  knowledge_points?: string[];
  created_at: string;
}

// --- Error Book ---
export type ErrorStatus = "not_explained" | "explained" | "pending_recall" | "recall_success" | "recall_fail";
export type ErrorType = "计算错误" | "概念不清" | "粗心" | "不会";
export type EntryReason = "wrong" | "not_know" | "repeated_wrong";

export interface ErrorBookItem {
  id: number;
  subject: { name: Subject; icon: string };
  question_content: string;
  question_image_url?: string;
  knowledge_points: string[];
  error_type: ErrorType;
  entry_reason: EntryReason;
  status: ErrorStatus;
  created_at: string;
  last_recall_at?: string;
  last_recall_result?: "success" | "fail";
}

export interface ErrorSummary {
  total: number;
  pending_recall_count: number;
  by_subject: Record<string, number>;
}

// --- Weekly Report ---
export interface WeeklyReport {
  id: number;
  week: string;
  usage_days: number;
  total_minutes: number;
  completed_tasks: number;
  task_completion_rate: number;
  fixed_errors: number;
  subject_performances: SubjectPerformance[];
  high_risk_points: string[];
  repeated_errors: string[];
  suggestions: string[];
  week_over_week: {
    usage_days_change: number;
    total_minutes_change: number;
    completion_rate_change: number;
  };
}

export interface SubjectPerformance {
  subject: Subject;
  risk_level: "stable" | "low_risk" | "medium_risk" | "high_risk";
  summary: string;
  knowledge_points_improved: string[];
  knowledge_points_declined: string[];
}

// --- Admin ---
export interface CorrectionItem {
  id: number;
  type: "ocr" | "knowledge" | "plan" | "qa";
  student_name: string;
  description: string;
  status: "pending" | "resolved" | "dismissed";
  created_at: string;
  original_data: Record<string, unknown>;
  corrected_data?: Record<string, unknown>;
}

export interface SystemMetrics {
  active_students: number;
  total_plans_today: number;
  total_qa_sessions_today: number;
  total_uploads_today: number;
  llm_calls_today: number;
  llm_cost_today: number;
  avg_response_time_ms: number;
  error_rate: number;
  ocr_success_rate: number;
  fallback_rate: number;
}

// --- Share ---
export interface ShareReport {
  student_nickname: string;
  week: string;
  usage_days: number;
  total_minutes: number;
  task_completion_rate: number;
  subject_summaries: { subject: Subject; risk_level: string; summary: string }[];
  suggestions: string[];
  generated_at: string;
}
