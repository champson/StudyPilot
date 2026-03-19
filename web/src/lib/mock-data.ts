// Mock data for development - mirrors API contract types
import type {
  DailyPlan,
  StudyUpload,
  QASession,
  QAMessage,
  ErrorBookItem,
  ErrorSummary,
  WeeklyReport,
  CorrectionItem,
  SystemMetrics,
  ShareReport,
} from "@/types/api";

export const mockDailyPlan: DailyPlan = {
  id: 1,
  plan_date: "2026-03-18",
  learning_mode: "workday_follow",
  available_minutes: 60,
  source: "history_inferred",
  status: "in_progress",
  recommended_subjects: [
    { name: "数学", reasons: ["今日校内同步"] },
    { name: "物理", reasons: ["本周反复出错"] },
    { name: "英语", reasons: ["本周覆盖不足"] },
  ],
  tasks: [
    {
      id: 1, sequence: 1,
      subject: { name: "数学", icon: "📐" },
      task_type: "error_review", title: "错题回顾",
      description: "回顾昨日错题：二次函数图像平移",
      reasons: ["本周反复出错"], estimated_minutes: 8,
      status: "completed", completed_at: "2026-03-18T14:30:00+08:00", duration_minutes: 8,
    },
    {
      id: 2, sequence: 2,
      subject: { name: "数学", icon: "📐" },
      task_type: "lecture", title: "知识点讲解",
      description: "学习知识点：二次函数的性质与图像",
      reasons: ["今日校内同步"], estimated_minutes: 15,
      status: "entered",
    },
    {
      id: 3, sequence: 3,
      subject: { name: "数学", icon: "📐" },
      task_type: "practice", title: "巩固练习",
      description: "完成 3 道同类型练习题",
      reasons: [], estimated_minutes: 10,
      status: "pending",
    },
    {
      id: 4, sequence: 4,
      subject: { name: "物理", icon: "⚡" },
      task_type: "error_review", title: "错题回顾",
      description: "回顾电磁感应相关错题",
      reasons: ["本周反复出错"], estimated_minutes: 12,
      status: "pending",
    },
    {
      id: 5, sequence: 5,
      subject: { name: "英语", icon: "📖" },
      task_type: "lecture", title: "阅读理解练习",
      description: "完成一篇阅读理解并分析",
      reasons: ["本周覆盖不足"], estimated_minutes: 15,
      status: "pending",
    },
  ],
  completed_tasks: 1,
  total_tasks: 5,
};

export const mockRecentUploads: StudyUpload[] = [
  { id: 1, upload_type: "homework", subject: "数学", file_urls: [], ocr_status: "completed", created_at: "2026-03-18T14:30:00+08:00" },
  { id: 2, upload_type: "note", subject: "物理", file_urls: [], ocr_status: "completed", created_at: "2026-03-17T16:20:00+08:00" },
  { id: 3, upload_type: "test", subject: "英语", file_urls: [], ocr_status: "completed", created_at: "2026-03-16T10:00:00+08:00" },
];

export const mockQAHistory: QASession[] = [
  { id: 1, subject: "数学", title: "三角函数求值", message_count: 6, created_at: "2026-03-18T15:20:00+08:00", updated_at: "2026-03-18T15:35:00+08:00" },
  { id: 2, subject: "物理", title: "电磁感应计算", message_count: 4, created_at: "2026-03-17T18:45:00+08:00", updated_at: "2026-03-17T19:00:00+08:00" },
];

export const mockQAMessages: QAMessage[] = [
  { id: 1, role: "assistant", content: "你好！我是你的 AI 学习助教，遇到不会的题可以随时问我。\n你可以直接输入问题，或者拍照上传题目。", created_at: "2026-03-18T15:20:00+08:00" },
  { id: 2, role: "user", content: "这道三角函数的题不会做，求解答", attachments: ["/mock/question.jpg"], created_at: "2026-03-18T15:21:00+08:00" },
  { id: 3, role: "assistant", content: "我来帮你分析这道题。\n\n**📌 题目分析**\n这是一道关于三角函数求值的题目，需要用到诱导公式和特殊角的值。\n\n**💡 解题思路**\n第一步：观察角度特点，把 sin(π+α) 用诱导公式转化\n第二步：利用已知条件 sinα = 3/5 求解\n\n你能先试着完成第一步吗？sin(π+α) 等于什么？", tutoring_strategy: "step_by_step", knowledge_points: ["诱导公式", "特殊角三角函数值"], created_at: "2026-03-18T15:21:30+08:00" },
  { id: 4, role: "user", content: "sin(π+α) = -sinα = -3/5", created_at: "2026-03-18T15:23:00+08:00" },
  { id: 5, role: "assistant", content: "✅ 完全正确！你已经掌握了诱导公式 sin(π+α) = -sinα\n\n现在继续第二步，我们需要求 cos(α)...", tutoring_strategy: "step_by_step", knowledge_points: ["诱导公式"], created_at: "2026-03-18T15:23:30+08:00" },
];

export const mockErrorSummary: ErrorSummary = {
  total: 30,
  pending_recall_count: 5,
  by_subject: { "数学": 12, "物理": 8, "英语": 5, "化学": 3, "语文": 2 },
};

export const mockErrors: ErrorBookItem[] = [
  {
    id: 1,
    subject: { name: "数学", icon: "📐" },
    question_content: "已知 sinα = 3/5，α ∈ (0, π/2)，求 sin(π+α) 的值。",
    knowledge_points: ["诱导公式", "特殊角三角函数值"],
    error_type: "概念不清", entry_reason: "wrong",
    status: "pending_recall",
    created_at: "2026-03-17T15:30:00+08:00",
  },
  {
    id: 2,
    subject: { name: "物理", icon: "⚡" },
    question_content: "如图所示，一个质量为 m 的物体放在倾角为 θ 的斜面上，求物体所受摩擦力。",
    knowledge_points: ["受力分析", "牛顿第二定律"],
    error_type: "计算错误", entry_reason: "not_know",
    status: "explained",
    created_at: "2026-03-16T10:20:00+08:00",
  },
  {
    id: 3,
    subject: { name: "数学", icon: "📐" },
    question_content: "二次函数 y = x² - 2x + 3 的顶点坐标为？",
    knowledge_points: ["二次函数图像", "顶点式"],
    error_type: "粗心", entry_reason: "wrong",
    status: "recall_success",
    created_at: "2026-03-15T14:00:00+08:00",
    last_recall_at: "2026-03-16T09:00:00+08:00",
    last_recall_result: "success",
  },
  {
    id: 4,
    subject: { name: "英语", icon: "📖" },
    question_content: "The manager insisted that all employees _____ (attend) the meeting.",
    knowledge_points: ["虚拟语气", "insist用法"],
    error_type: "概念不清", entry_reason: "wrong",
    status: "pending_recall",
    created_at: "2026-03-17T09:00:00+08:00",
  },
  {
    id: 5,
    subject: { name: "化学", icon: "🧪" },
    question_content: "写出 Na₂O₂ 与 H₂O 反应的化学方程式。",
    knowledge_points: ["过氧化钠", "氧化还原反应"],
    error_type: "不会", entry_reason: "not_know",
    status: "not_explained",
    created_at: "2026-03-18T08:00:00+08:00",
  },
];

export const mockWeeklyReport: WeeklyReport = {
  id: 1, week: "2026-W11",
  usage_days: 5, total_minutes: 272, completed_tasks: 23,
  task_completion_rate: 78, fixed_errors: 15,
  subject_performances: [
    { subject: "数学", risk_level: "low_risk", summary: "二次函数掌握度提升，但三角函数仍需加强", knowledge_points_improved: ["二次函数图像"], knowledge_points_declined: ["三角函数求值"] },
    { subject: "物理", risk_level: "medium_risk", summary: "力学部分有明显进步，电磁感应仍为薄弱点", knowledge_points_improved: ["牛顿定律"], knowledge_points_declined: ["电磁感应"] },
    { subject: "英语", risk_level: "stable", summary: "阅读理解保持稳定，语法填空需要关注", knowledge_points_improved: [], knowledge_points_declined: ["虚拟语气"] },
    { subject: "化学", risk_level: "low_risk", summary: "氧化还原反应理解有所提升", knowledge_points_improved: ["氧化还原反应"], knowledge_points_declined: [] },
    { subject: "语文", risk_level: "stable", summary: "文言文阅读维持现状", knowledge_points_improved: [], knowledge_points_declined: [] },
  ],
  high_risk_points: ["三角函数诱导公式", "电磁感应定律", "虚拟语气"],
  repeated_errors: ["诱导公式符号判断", "受力分析遗漏力"],
  suggestions: [
    "本周重点巩固三角函数诱导公式，建议每天安排 1-2 道相关练习",
    "物理电磁感应部分建议回顾基础概念，从法拉第定律出发重新梳理",
    "英语虚拟语气可通过固定句型记忆来突破",
  ],
  week_over_week: {
    usage_days_change: 1,
    total_minutes_change: 45,
    completion_rate_change: -5,
  },
};

export const mockCorrections: CorrectionItem[] = [
  { id: 1, type: "ocr", student_name: "小明", description: "数学作业 OCR 识别错误：公式 sin²α 被识别为 sin2α", status: "pending", created_at: "2026-03-18T10:00:00+08:00", original_data: { text: "sin2α" }, corrected_data: undefined },
  { id: 2, type: "knowledge", student_name: "小明", description: "知识点状态异常：'二次函数图像' 从基本掌握突降为初步接触", status: "pending", created_at: "2026-03-18T09:30:00+08:00", original_data: { from: "基本掌握", to: "初步接触" } },
  { id: 3, type: "plan", student_name: "小红", description: "今日计划推荐了已标记为稳定的学科", status: "resolved", created_at: "2026-03-17T14:00:00+08:00", original_data: {}, corrected_data: { action: "removed_subject" } },
];

export const mockMetrics: SystemMetrics = {
  active_students: 4,
  total_plans_today: 4,
  total_qa_sessions_today: 12,
  total_uploads_today: 8,
  llm_calls_today: 156,
  llm_cost_today: 12.5,
  avg_response_time_ms: 1250,
  error_rate: 2.1,
  ocr_success_rate: 94.5,
  fallback_rate: 8.3,
};

export const mockShareReport: ShareReport = {
  student_nickname: "小明",
  week: "2026-W11",
  usage_days: 5,
  total_minutes: 272,
  task_completion_rate: 78,
  subject_summaries: [
    { subject: "数学", risk_level: "low_risk", summary: "本周数学整体表现良好，二次函数掌握度提升" },
    { subject: "物理", risk_level: "medium_risk", summary: "力学有进步，电磁感应仍需关注" },
    { subject: "英语", risk_level: "stable", summary: "阅读理解保持稳定" },
  ],
  suggestions: [
    "建议继续保持每日学习习惯",
    "物理电磁感应部分需要额外关注",
  ],
  generated_at: "2026-03-18T08:00:00+08:00",
};
