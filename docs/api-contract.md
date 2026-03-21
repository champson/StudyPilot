# API 契约规范

本文档是 `docs/api-openapi.yaml`（机器可读规范）的工程实现层补充，提供：
- TypeScript 类型定义（前后端共用）
- 每个端点的完整 JSON 请求/响应示例
- 完整错误码注册表
- 认证流程详细说明
- 接口版本管理策略

---

## 目录

1. [全局约定](#1-全局约定)
2. [认证机制](#2-认证机制)
3. [统一响应结构](#3-统一响应结构)
4. [错误码注册表](#4-错误码注册表)
5. [TypeScript 核心类型定义](#5-typescript-核心类型定义)
6. [学生端 API 契约](#6-学生端-api-契约)
7. [家长端 API 契约](#7-家长端-api-契约)
8. [分享链接 API 契约](#8-分享链接-api-契约)
9. [管理端 API 契约](#9-管理端-api-契约)
10. [版本管理策略](#10-版本管理策略)

---

## 1. 全局约定

### 1.1 基础 URL

```
生产环境:  https://api.studypilot.example.com/api/v1
本地开发:  http://localhost:8000/api/v1
```

### 1.2 请求头规范

所有需要认证的请求必须携带：

```http
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
Accept: application/json
X-Request-ID: <uuid-v4>          # 可选，链路追踪用
```

流式端点（SSE）额外要求：
```http
Accept: text/event-stream
Cache-Control: no-cache
```

文件上传端点：
```http
Content-Type: multipart/form-data  # 浏览器自动设置 boundary
```

### 1.3 时间格式

- 所有时间字段使用 **ISO 8601** 格式，带时区：`2026-03-18T14:30:00+08:00`
- 纯日期字段：`2026-03-18`
- 周标识：`2026-W11`（ISO 周编号）

### 1.4 分页规范

所有列表接口统一使用页码分页：

**请求参数：**
```
page      integer  页码，从 1 开始，默认 1
page_size integer  每页条数，默认 20，最大 100
```

**响应结构：**
```json
{
  "data": { "items": [...], "page": 1, "page_size": 20, "total": 87, "total_pages": 5 }
}
```

**参数校验约束：**
- `page`：最小值 1，传入 ≤0 返回 `SYS_INVALID_PAGINATION`
- `page_size`：最小值 1，最大值 100，超出范围返回 `SYS_INVALID_PAGINATION`
- 后端实现应使用 `Query(ge=1)` 和 `Query(ge=1, le=100)` 约束

### 1.5 HTTP 状态码使用规范

| 状态码 | 场景 |
|--------|------|
| `200 OK` | 成功的 GET / PATCH |
| `201 Created` | 成功的 POST（创建新资源）|
| `202 Accepted` | 异步任务已接受（OCR 上传）|
| `204 No Content` | 成功但无响应体（不使用）|
| `400 Bad Request` | 请求参数不合法 |
| `401 Unauthorized` | 未认证或 Token 失效 |
| `403 Forbidden` | 已认证但无权限 |
| `404 Not Found` | 资源不存在 |
| `409 Conflict` | 资源冲突（重复创建）|
| `422 Unprocessable Entity` | 业务规则校验失败（优先用 400）|
| `429 Too Many Requests` | 限流 |
| `500 Internal Server Error` | 服务内部错误 |
| `503 Service Unavailable` | LLM 服务不可用（降级）|

### 1.6 软删除约定

数据库对 `daily_plans`、`study_uploads`、`error_book` 使用 `is_deleted` 字段实现软删除。

- **所有列表 API 默认只返回 `is_deleted = false` 的记录**，无需调用方传参。
- 学生端不提供删除接口（无 DELETE 端点），`is_deleted` 由管理员后台操作使用。
- 管理员通过后台将记录标记为已删除，操作不可逆（当前版本无恢复接口）。

---

## 2. 认证机制

### 2.1 角色与 Token 体系

```
┌─────────┬──────────────────────┬─────────────────────────────┐
│ 角色    │ 获取方式              │ JWT Payload                 │
├─────────┼──────────────────────┼─────────────────────────────┤
│ student │ POST /auth/token-login│ { role, user_id, student_id}│
│ parent  │ POST /auth/token-login│ { role, user_id, student_id}│
│ admin   │ POST /auth/admin-login│ { role, user_id }           │
│ share   │ 内嵌在 URL path 中    │ { student_id, week, exp }   │
└─────────┴──────────────────────┴─────────────────────────────┘
```

### 2.2 学生/家长登录

**`POST /auth/token-login`**

**请求体：**
```json
{
  "token": "student_abc123xyz",
  "role": "student"
}
```

**成功响应 `200`：**
```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 2592000,
    "user": {
      "id": 1,
      "role": "student",
      "nickname": "小明",
      "student_id": 3
    }
  }
}
```

**错误响应 `401`：**
```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Token 无效或已被停用",
    "detail": {}
  }
}
```

### 2.3 管理员登录

**`POST /auth/admin-login`**

**请求体：**
```json
{
  "username": "admin",
  "password": "••••••••"
}
```

**成功响应 `200`：** 同 2.2，`role` 为 `"admin"`，`student_id` 为 `null`。

### 2.4 JWT Payload 结构

```typescript
interface JwtPayload {
  sub: string;          // user_id（字符串形式）
  user_id: number;
  role: "student" | "parent" | "admin";
  student_id: number | null;   // parent 绑定的学生 ID
  iat: number;          // 签发时间（Unix 时间戳）
  exp: number;          // 过期时间（Unix 时间戳）
}

// 分享链接专用 Payload
interface ShareJwtPayload {
  student_id: number;
  report_week: string;   // "2026-W11"
  iat: number;
  exp: number;
}
```

### 2.5 Token 有效期

| 角色 | 有效期 | 说明 |
|------|--------|------|
| student / parent | 30 天 | 长期有效，简化自用场景 |
| admin | 24 小时 | 安全考虑，每日重新登录 |
| share | 7 天（可配置 1-30 天）| 生成时指定 |

### 2.6 认证失败处理

Token 失效（过期/无效）时，前端应：
1. 清除本地存储的 Token
2. 重定向至登录页
3. 不自动重试原请求

### 2.7 Token 刷新

#### `POST /auth/refresh`

使用有效的 Access Token 换取新 Token，延长登录会话。

**请求头：**
```http
Authorization: Bearer <CURRENT_ACCESS_TOKEN>
```

**请求体：** 无（空 JSON `{}`）

**成功响应 `200`：**
```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 2592000,
    "refreshed_at": "2026-03-18T14:30:00+08:00"
  }
}
```

**刷新规则：**

| 角色 | 刷新窗口 | 说明 |
|------|---------|------|
| student / parent | Token 过期前 7 天内可刷新 | 过期后不可刷新，需重新登录 |
| admin | Token 过期前 2 小时内可刷新 | 安全考虑，窗口较短 |

**错误响应 `401`（不在刷新窗口内）：**
```json
{
  "error": {
    "code": "AUTH_REFRESH_NOT_ALLOWED",
    "message": "当前 Token 尚未进入刷新窗口，或已过期",
    "detail": {
      "expires_at": "2026-04-17T14:30:00+08:00",
      "refresh_window_starts": "2026-04-10T14:30:00+08:00"
    }
  }
}
```

**前端实现建议：**
- 在每次 API 请求时检查 Token 剩余有效期
- 剩余 <7 天时自动调用 `/auth/refresh` 静默续期
- 续期失败时不影响当前请求，下次请求再重试

---

## 3. 统一响应结构

### 3.1 成功响应

所有成功响应统一包裹在 `data` 字段中：

```typescript
interface SuccessResponse<T> {
  data: T;
  meta?: {
    request_id?: string;
    server_time?: string;   // ISO 8601
  };
}
```

**示例：**
```json
{
  "data": {
    "id": 42,
    "plan_date": "2026-03-18",
    "status": "generated"
  }
}
```

### 3.2 分页成功响应

```typescript
interface PaginatedResponse<T> {
  data: {
    items: T[];
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}
```

**示例：**
```json
{
  "data": {
    "items": [
      { "id": 1, "subject_name": "数学", "recall_count": 2 }
    ],
    "page": 1,
    "page_size": 20,
    "total": 43,
    "total_pages": 3
  }
}
```

### 3.3 错误响应

```typescript
interface ErrorResponse {
  error: {
    code: string;           // 大写下划线，全局唯一
    message: string;        // 人类可读，可直接展示给用户
    detail: Record<string, unknown>;  // 调试用附加信息
  };
}
```

**示例：**
```json
{
  "error": {
    "code": "ONBOARDING_NOT_COMPLETED",
    "message": "请先完成入学问卷，才能生成个性化学习计划",
    "detail": {
      "redirect": "/onboarding"
    }
  }
}
```

### 3.4 异步任务响应（202）

```typescript
interface AsyncTaskResponse {
  data: {
    task_id?: string;       // Celery 任务 ID（可选）
    resource_id: number;    // 创建的资源 ID（如 upload_id）
    status: string;         // 初始状态（如 "pending"）
    poll_url: string;       // 轮询状态的完整 URL
    message: string;        // 对用户的提示信息
  };
}
```

**示例（上传后返回）：**
```json
{
  "data": {
    "resource_id": 456,
    "status": "pending",
    "poll_url": "/api/v1/student/material/456/ocr-status",
    "message": "文件已上传，正在识别中，请稍后查询结果"
  }
}
```

---

## 4. 错误码注册表

### 4.1 认证类 (AUTH_*)

| 错误码 | HTTP | 说明 | 前端处理 |
|--------|------|------|---------|
| `AUTH_INVALID_TOKEN` | 401 | Token 无效或不存在 | 跳登录页 |
| `AUTH_TOKEN_EXPIRED` | 401 | Token 已过期 | 跳登录页 |
| `AUTH_INSUFFICIENT_ROLE` | 403 | 角色权限不足 | 展示无权限提示 |
| `AUTH_SHARE_TOKEN_EXPIRED` | 401 | 分享链接已过期 | 展示"链接已失效" |
| `AUTH_SHARE_TOKEN_INVALID` | 401 | 分享链接无效 | 展示"链接无效" |
| `AUTH_REFRESH_NOT_ALLOWED` | 401 | Token 不在可刷新窗口内 | 忽略或跳登录页 |

### 4.2 用户档案类 (PROFILE_*)

| 错误码 | HTTP | 说明 |
|--------|------|------|
| `PROFILE_ALREADY_EXISTS` | 409 | 档案已存在 |
| `PROFILE_NOT_FOUND` | 404 | 档案不存在 |
| `PROFILE_INVALID_GRADE` | 400 | 年级值非法 |
| `PROFILE_INVALID_SUBJECT_COMBINATION` | 400 | 选科组合不合法 |

### 4.3 入学问卷类 (ONBOARDING_*)

| 错误码 | HTTP | 说明 |
|--------|------|------|
| `ONBOARDING_NOT_COMPLETED` | 400 | 未完成入学问卷（阻止生成计划）|
| `ONBOARDING_ALREADY_COMPLETED` | 409 | 问卷已完成，不可重复提交 |
| `ONBOARDING_INVALID_WEAK_SUBJECTS` | 400 | 薄弱学科超过 3 门 |
| `ONBOARDING_INVALID_SCORE` | 400 | 成绩值超出合法范围 |

### 4.4 计划类 (PLAN_*)

| 错误码 | HTTP | 说明 |
|--------|------|------|
| `PLAN_GENERATION_FAILED` | 503 | 计划生成失败（LLM 不可用）|
| `PLAN_NOT_FOUND` | 404 | 今日无计划 |
| `PLAN_TASK_NOT_FOUND` | 404 | 任务不存在 |
| `PLAN_INVALID_STATUS_TRANSITION` | 400 | 状态不合法（仅禁止逆向回退，如 completed→entered；允许从任意状态直接跳到 completed）|
| `PLAN_INVALID_MODE` | 400 | 模式值非法 |
| `PLAN_ALREADY_EXISTS` | 409 | 今日计划已存在（需 force_regenerate）|

### 4.5 上传类 (UPLOAD_*)

| 错误码 | HTTP | 说明 |
|--------|------|------|
| `UPLOAD_FILE_TOO_LARGE` | 400 | 文件超过 20MB |
| `UPLOAD_UNSUPPORTED_FORMAT` | 400 | 文件格式不支持 |
| `UPLOAD_OSS_FAILED` | 503 | OSS 写入失败 |
| `UPLOAD_NOT_FOUND` | 404 | 上传记录不存在 |
| `UPLOAD_OCR_NOT_FAILED` | 400 | 重试 OCR 时原状态非 failed |
| `UPLOAD_OCR_MAX_RETRY_EXCEEDED` | 400 | 已超过最大重试次数 |

### 4.6 答疑类 (QA_*)

| 错误码 | HTTP | 说明 |
|--------|------|------|
| `QA_SESSION_NOT_FOUND` | 404 | 会话不存在 |
| `QA_SESSION_CLOSED` | 400 | 向已关闭会话发送消息 |
| `QA_LLM_UNAVAILABLE` | 503 | LLM 服务不可用（已降级仍失败）|
| `QA_MESSAGE_TOO_LONG` | 400 | 消息超过长度限制 |
| `QA_ATTACHMENT_NOT_FOUND` | 400 | 附件 upload_id 不存在 |

### 4.7 错题本类 (ERROR_BOOK_*)

| 错误码 | HTTP | 说明 |
|--------|------|------|
| `ERROR_BOOK_ITEM_NOT_FOUND` | 404 | 错题不存在 |
| `ERROR_BOOK_RECALL_BATCH_TOO_LARGE` | 400 | 批量召回超过 20 题 |

### 4.8 系统类 (SYS_*)

| 错误码 | HTTP | 说明 |
|--------|------|------|
| `SYS_INTERNAL_ERROR` | 500 | 服务内部错误 |
| `SYS_SERVICE_UNAVAILABLE` | 503 | 服务暂不可用 |
| `SYS_RATE_LIMITED` | 429 | 请求过于频繁 |
| `SYS_INVALID_PAGINATION` | 400 | 分页参数非法 |

---

## 5. TypeScript 核心类型定义

> 这些类型应放在前端项目 `src/types/api.ts` 中，后端 Pydantic 模型与之对应。

```typescript
// ============================================================
// 通用结构
// ============================================================

export interface ApiSuccessResponse<T> {
  data: T;
}

export interface ApiPaginatedResponse<T> {
  data: {
    items: T[];
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    detail: Record<string, unknown>;
  };
}

export interface AsyncTaskResponse {
  data: {
    resource_id: number;
    status: string;
    poll_url: string;
    message: string;
  };
}

// ============================================================
// 枚举
// ============================================================

export type UserRole = "student" | "parent" | "admin";

export type LearningMode = "workday_follow" | "weekend_review";

export type PlanSource =
  | "upload_corrected"
  | "history_inferred"
  | "manual_adjusted"
  | "generic_fallback";

export type PlanStatus = "generated" | "in_progress" | "completed";

export type TaskStatus = "pending" | "entered" | "executed" | "completed";

export type TaskType =
  | "lecture"
  | "practice"
  | "error_review"
  | "consolidation";

export type OcrStatus = "pending" | "processing" | "completed" | "failed";

export type UploadType = "note" | "homework" | "test" | "handout" | "score";

export type KnowledgeStatus =
  | "未观察"
  | "初步接触"
  | "需要巩固"
  | "基本掌握"
  | "反复失误";

export type RiskLevel = "稳定" | "轻度风险" | "中度风险" | "高风险";

export type ErrorType =
  | "calc_error"
  | "concept_unclear"
  | "careless"
  | "unknown";

export type EntryReason = "wrong" | "not_know" | "repeated_wrong";

export type RecallResult = "success" | "fail";

export type TutoringStrategy =
  | "hint"
  | "step_by_step"
  | "formula"
  | "full_solution";

export type MessageIntent =
  | "upload_question"
  | "ask"
  | "follow_up"
  | "chat";

export type QaSessionStatus = "active" | "closed";

export type RunMode = "normal" | "best";

export type CorrectionTargetType = "ocr" | "knowledge" | "plan" | "qa";

// 推荐原因标签：严格枚举，复用 architecture_design.md PriorityFactor 定义
// 工作日模式因素
export type PriorityFactor =
  | "今日校内同步"
  | "今日错误较多"
  | "明日任务/测验"
  | "近期反复错误"
  | "本周覆盖不足"
  // 周末模式因素
  | "本周错题修复"
  | "薄弱知识点待修复"
  | "考试临近"
  | "最近成绩下滑";

// 知识点状态变更触发类型（与 student_knowledge_status.last_update_reason 值一致）
export type TriggerType =
  | "quiz_correct"
  | "quiz_wrong"
  | "recall_success"
  | "recall_fail"
  | "manual";

// ============================================================
// 认证
// ============================================================

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: {
    id: number;
    role: UserRole;
    nickname: string;
    student_id: number | null;
  };
}

export interface RefreshTokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  refreshed_at: string;
}

// ============================================================
// 学生档案
// ============================================================

export interface StudentProfile {
  id: number;
  user_id: number;
  grade: "高一" | "高二" | "高三";
  textbook_version: string | null;
  subject_combination: string[];
  upcoming_exams: UpcomingExam[];
  onboarding_completed: boolean;
  created_at: string;
  updated_at: string;
}

export interface UpcomingExam {
  name: string;
  date: string;
}

export interface OnboardingSubmitRequest {
  grade: "高一" | "高二" | "高三";
  textbook_version?: Record<string, string>;
  subject_combination: string[];
  weak_subjects: string[];              // 最多 3 门
  recent_exam_scores?: Record<string, number>;
  error_types_by_subject?: Record<string, ErrorType[]>;
  daily_study_minutes: number;
  upcoming_exam_date?: string | null;
}

export interface OnboardingSubmitResponse {
  onboarding_completed: true;
  initialized_knowledge_points: number;
  initialized_subject_risks: Array<{
    subject_code: string;
    risk_level: RiskLevel;
  }>;
}

// ============================================================
// 学习计划
// ============================================================

export interface DailyPlan {
  id: number;
  plan_date: string;
  learning_mode: LearningMode;
  system_recommended_mode: LearningMode;
  available_minutes: number;
  source: PlanSource;
  is_history_inferred: boolean;
  recommended_subjects: RecommendedSubject[];
  tasks: PlanTask[];        // 任务列表，从 plan_tasks 表读取；数据库的 plan_content JSONB 是后端内部字段，不暴露给 API
  status: PlanStatus;
  warning: string | null;
  created_at: string;
}

export interface RecommendedSubject {
  subject_id: number;
  subject_name: string;
  reasons: PriorityFactor[];  // 严格枚举，前端可据此做本地化/样式化处理
}

export interface PlanTask {
  id: number;
  plan_id: number;
  subject_id: number;
  subject_name: string;
  task_type: TaskType;
  task_content: TaskContent;
  sequence: number;
  estimated_minutes: number;
  status: TaskStatus;
  started_at: string | null;
  completed_at: string | null;
  duration_minutes: number | null;
}

export interface TaskContent {
  description: string;
  knowledge_point_ids?: number[];
  error_ids?: number[];            // error_review 类型时有值
  source_material_id?: number;     // 关联上传材料
}

// ============================================================
// 上传与 OCR
// ============================================================

export interface StudyUpload {
  id: number;
  upload_type: UploadType;
  original_url: string;       // OSS 原始文件 URL（学生只读，权限矩阵 §3）
  thumbnail_url: string | null;
  subject_id: number | null;
  subject_name: string | null;
  ocr_status: OcrStatus;
  is_manual_corrected: boolean;
  created_at: string;
  // file_hash 是服务端内部字段，不通过 API 暴露
}

export interface OcrStatusResponse {
  upload_id: number;
  ocr_status: OcrStatus;
  ocr_result: OcrResult | null;
  ocr_error: string | null;
}

export interface OcrResult {
  extracted_questions: ExtractedQuestion[];
  subject_detected: string | null;
  knowledge_points: Array<{
    id: number;
    name: string;
    confidence: number;
  }>;
}

export interface ExtractedQuestion {
  question_text: string;
  latex_expressions: string[];
  question_type: string | null;
}

// ============================================================
// 答疑
// ============================================================

export interface ChatRequest {
  session_id: number | null;
  message: string;
  attachments?: ChatAttachment[];
  subject_id?: number | null;
}

export interface ChatAttachment {
  type: "image";
  upload_id: number;
}

export interface ChatResponse {
  session_id: number;
  message_id: number;
  role: "assistant";
  content: string;
  knowledge_points: Array<{ id: number; name: string }>;
  tutoring_strategy: TutoringStrategy | null;
}

// SSE chunk 事件类型（流式响应）
export type SseEvent =
  | { type: "session_created"; session_id: number }
  | { type: "chunk"; content: string }
  | { type: "knowledge_points"; data: Array<{ id: number; name: string }> }
  | { type: "strategy"; data: TutoringStrategy }
  | { type: "error"; code: string; message: string };

export interface QaSession {
  id: number;
  session_date: string;
  subject_id: number | null;
  subject_name: string | null;
  status: QaSessionStatus;
  message_count: number;
  created_at: string;
  closed_at: string | null;
}

export interface QaSessionDetail extends QaSession {
  messages: QaMessage[];
}

export interface QaMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  attachments: ChatAttachment[];
  intent: MessageIntent | null;
  knowledge_points: Array<{ id: number; name: string }>;
  tutoring_strategy: TutoringStrategy | null;
  created_at: string;
}

// ============================================================
// 错题本
// ============================================================

export interface ErrorBookItem {
  id: number;
  subject_id: number;
  subject_name: string;
  question_content: QuestionContent;
  knowledge_points: Array<{ id: number; name: string }>;
  error_type: ErrorType | null;
  entry_reason: EntryReason;
  is_explained: boolean;
  is_recalled: boolean;
  last_recall_at: string | null;
  last_recall_result: RecallResult | null;
  recall_count: number;
  created_at: string;
}

export interface QuestionContent {
  text: string;
  latex_expressions: string[];
}

export interface ErrorSummary {
  total: number;
  unrecalled: number;
  by_subject: Array<{
    subject_id: number;
    subject_name: string;
    count: number;
    unrecalled: number;
  }>;
  by_error_type: Record<ErrorType, number>;
}

// ============================================================
// 知识点状态
// ============================================================

export interface KnowledgeStatusItem {
  knowledge_point_id: number;
  knowledge_point_name: string;
  subject_name: string;
  level: 1 | 2 | 3;
  status: KnowledgeStatus;
  importance_score: number;
  last_updated_at: string;
  is_manual_corrected: boolean;
}

export interface KnowledgeStatusOverview {
  total: number;
  by_status: Record<KnowledgeStatus, number>;
  items: KnowledgeStatusItem[];
}

// ============================================================
// 周报
// ============================================================

export interface SubjectRisk {
  subject_id: number;
  subject_name: string;
  risk_level: RiskLevel;
  effective_week: string;
}

export interface WeeklyReportStudent {
  report_week: string;
  usage_days: number;
  total_minutes: number;
  task_completion_rate: number;
  subject_trends: Array<{
    subject_name: string;
    risk_level: RiskLevel;
    trend: "improving" | "stable" | "declining";
  }>;
  high_risk_knowledge_points: Array<{
    name: string;
    subject_name: string;
    status: KnowledgeStatus;
  }>;
  repeated_error_points: Array<{
    name: string;
    error_count: number;
  }>;
  next_stage_suggestions: string[];
  class_rank: number | null;
  grade_rank: number | null;
  share_token: string | null;
}

export interface WeeklyReportParent {
  report_week: string;
  student_name: string;
  usage_days: number;
  total_minutes: number;
  task_completion_rate: number;
  subject_risks: SubjectRisk[];
  trend_description: string;
  action_suggestions: string[];
  class_rank: number | null;
  grade_rank: number | null;
  share_token: string | null;
}

// ============================================================
// 分享内容（脱敏）
// ============================================================

export interface ShareContent {
  student_name: string;           // 昵称，如"小明"
  report_week: string;
  usage_days: number;
  total_minutes: number;
  trend_overview: string;
  subject_risk_overview: Array<{
    subject_name: string;
    risk_level: RiskLevel;
  }>;
  next_stage_suggestions_summary: string;
  expires_at: string;
}

// ============================================================
// 管理端
// ============================================================

export interface SystemMode {
  current_mode: RunMode;
  switched_at: string | null;
  switched_by: string | null;
}

export interface TodayMetrics {
  date: string;
  active_users: number;
  plans_generated: number;
  uploads_count: number;
  qa_sessions: number;
  total_api_requests: number;
  api_error_rate: number;
  current_mode: RunMode;
  estimated_cost_today: number;
  pending_corrections: number;
}

export type CorrectionStatus = "pending" | "resolved" | "rejected";

export interface CorrectionItem {
  id: number;
  target_type: CorrectionTargetType;
  target_id: number;
  original_content: unknown | null;
  corrected_content: unknown;
  correction_reason: string | null;
  status: CorrectionStatus;
  corrected_by: number;
  created_at: string;
}

// ============================================================
// structured_summary（Assessment Agent 输出，存于 qa_sessions）
// ============================================================

export interface StructuredSummary {
  session_id: number;
  assessed_at: string;
  knowledge_point_updates: KnowledgePointUpdate[];
  session_summary: SessionSummary;
  suggested_followup: string;
}

export interface KnowledgePointUpdate {
  knowledge_point_id: number;
  knowledge_point_name: string;
  previous_status: KnowledgeStatus;
  new_status: KnowledgeStatus;
  reason: string;
  confidence: number;         // 0.0-1.0
}

export interface SessionSummary {
  total_questions: number;
  correct_first_try: number;
  correct_with_hint: number;
  incorrect: number;
  dominant_error_type: string | null;
}
```

---

## 6. 学生端 API 契约

### 6.1 入学问卷

#### `POST /student/onboarding/submit`

**请求示例：**
```json
{
  "grade": "高二",
  "textbook_version": {
    "math": "人教A版",
    "physics": "人教版",
    "chemistry": "人教版"
  },
  "subject_combination": ["physics", "chemistry", "biology"],
  "weak_subjects": ["math", "physics"],
  "recent_exam_scores": {
    "chinese": 118,
    "math": 92,
    "english": 135,
    "physics": 62,
    "chemistry": 78
  },
  "error_types_by_subject": {
    "math": ["calc_error", "concept_unclear"],
    "physics": ["concept_unclear"]
  },
  "daily_study_minutes": 120,
  "upcoming_exam_date": "2026-04-15"
}
```

**成功响应 `200`：**
```json
{
  "data": {
    "onboarding_completed": true,
    "initialized_knowledge_points": 156,
    "initialized_subject_risks": [
      { "subject_code": "math", "risk_level": "轻度风险" },
      { "subject_code": "physics", "risk_level": "中度风险" }
    ]
  }
}
```

**错误响应 `409`（已完成）：**
```json
{
  "error": {
    "code": "ONBOARDING_ALREADY_COMPLETED",
    "message": "入学问卷已完成，如需修改请联系管理员",
    "detail": { "completed_at": "2026-03-10T09:30:00+08:00" }
  }
}
```

---

### 6.2 今日学习计划

#### `POST /student/plan/generate`

**请求示例：**
```json
{
  "available_minutes": 90,
  "learning_mode": "workday_follow",
  "force_regenerate": false
}
```

**成功响应 `200`：**
```json
{
  "data": {
    "id": 201,
    "plan_date": "2026-03-18",
    "learning_mode": "workday_follow",
    "system_recommended_mode": "workday_follow",
    "available_minutes": 90,
    "source": "upload_corrected",
    "is_history_inferred": false,
    "recommended_subjects": [
      {
        "subject_id": 2,
        "subject_name": "数学",
        "reasons": ["今日校内同步", "近期反复错误"]
      },
      {
        "subject_id": 4,
        "subject_name": "物理",
        "reasons": ["今日错误较多"]
      }
    ],
    "tasks": [
      {
        "id": 501,
        "plan_id": 201,
        "subject_id": 2,
        "subject_name": "数学",
        "task_type": "error_review",
        "task_content": {
          "description": "复习今日函数定义域相关错题",
          "knowledge_point_ids": [42, 43],
          "error_ids": [88, 92]
        },
        "sequence": 1,
        "estimated_minutes": 30,
        "status": "pending",
        "started_at": null,
        "completed_at": null,
        "duration_minutes": null
      },
      {
        "id": 502,
        "plan_id": 201,
        "subject_id": 4,
        "subject_name": "物理",
        "task_type": "practice",
        "task_content": {
          "description": "牛顿第二定律专项练习",
          "knowledge_point_ids": [115],
          "error_ids": []
        },
        "sequence": 2,
        "estimated_minutes": 40,
        "status": "pending",
        "started_at": null,
        "completed_at": null,
        "duration_minutes": null
      }
    ],
    "status": "generated",
    "warning": null,
    "created_at": "2026-03-18T16:00:00+08:00"
  }
}
```

**错误响应 `400`（问卷未完成）：**
```json
{
  "error": {
    "code": "ONBOARDING_NOT_COMPLETED",
    "message": "请先完成入学问卷，才能生成个性化学习计划",
    "detail": { "redirect": "/onboarding" }
  }
}
```

**降级响应 `200`（generic_fallback，连续 7 天无上传）：**
```json
{
  "data": {
    "id": 202,
    "source": "generic_fallback",
    "is_history_inferred": true,
    "warning": "连续7天未上传新内容，建议补充上传以恢复个性化准确度",
    "recommended_subjects": [
      {
        "subject_id": 2,
        "subject_name": "数学",
        "reasons": ["本周覆盖不足"]
      }
    ],
    "tasks": [...]
  }
}
```

#### `PATCH /student/plan/tasks/{taskId}`

**请求示例（进入任务）：**
```json
{
  "status": "entered"
}
```

**请求示例（完成任务）：**
```json
{
  "status": "completed",
  "duration_minutes": 28
}
```

**成功响应 `200`：**
```json
{
  "data": {
    "id": 501,
    "status": "completed",
    "started_at": "2026-03-18T19:15:00+08:00",
    "completed_at": "2026-03-18T19:43:00+08:00",
    "duration_minutes": 28
  }
}
```

**任务状态机规则：**

- 允许向前跳跃：`pending → completed`（学生可跳过中间步骤直接完成）
- 允许逐步推进：`pending → entered → executed → completed`
- **禁止逆向回退**：已进入 `completed` 后不可回退到任何前置状态

**错误响应 `400`（状态逆向回退）：**
```json
{
  "error": {
    "code": "PLAN_INVALID_STATUS_TRANSITION",
    "message": "任务状态不可回退，不可从 completed 切换到 entered",
    "detail": {
      "current_status": "completed",
      "requested_status": "entered",
      "allowed_transitions": []
    }
  }
}
```

---

### 6.3 学习材料上传

#### `POST /student/material/upload`

**请求（multipart/form-data）：**
```
file:        <binary>
upload_type: test
subject_id:  2
```

**成功响应 `202`：**
```json
{
  "data": {
    "resource_id": 456,
    "status": "pending",
    "poll_url": "/api/v1/student/material/456/ocr-status",
    "message": "文件已上传，正在识别中，请稍后查询结果"
  }
}
```

#### `GET /student/material/{id}/ocr-status`

**轮询响应 — 处理中 `200`：**
```json
{
  "data": {
    "upload_id": 456,
    "ocr_status": "processing",
    "ocr_result": null,
    "ocr_error": null
  }
}
```

**轮询响应 — 完成 `200`：**
```json
{
  "data": {
    "upload_id": 456,
    "ocr_status": "completed",
    "ocr_result": {
      "extracted_questions": [
        {
          "question_text": "设函数 $f(x) = \\sqrt{x-1}$，求其定义域。",
          "latex_expressions": ["\\sqrt{x-1}"],
          "question_type": "解答题"
        }
      ],
      "subject_detected": "数学",
      "knowledge_points": [
        { "id": 42, "name": "函数的定义域", "confidence": 0.92 },
        { "id": 38, "name": "不等式基础", "confidence": 0.75 }
      ]
    },
    "ocr_error": null
  }
}
```

**轮询响应 — 失败 `200`：**
```json
{
  "data": {
    "upload_id": 456,
    "ocr_status": "failed",
    "ocr_result": null,
    "ocr_error": "图片分辨率过低，无法识别文字"
  }
}
```

> **前端轮询策略**：每 3 秒轮询一次，最多 20 次（60 秒超时）。
> 超时后展示"识别超时，请稍后刷新"，不自动重试。

#### `POST /student/material/{id}/retry-ocr`

OCR 失败后，学生手动触发重试（仅当 `ocr_status=failed` 且重试次数未超上限时有效）。

**请求体：** 无（空 JSON `{}`）

**成功响应 `202`：**
```json
{
  "data": {
    "resource_id": 456,
    "status": "pending",
    "poll_url": "/api/v1/student/material/456/ocr-status",
    "message": "已重新提交识别任务，请稍后查询结果"
  }
}
```

**错误响应 `400`（原状态非 failed）：**
```json
{
  "error": {
    "code": "UPLOAD_OCR_NOT_FAILED",
    "message": "当前 OCR 状态为 processing，无需重试",
    "detail": { "current_ocr_status": "processing" }
  }
}
```

**错误响应 `400`（超过最大重试次数）：**
```json
{
  "error": {
    "code": "UPLOAD_OCR_MAX_RETRY_EXCEEDED",
    "message": "已超过最大重试次数（3次），请联系管理员处理",
    "detail": { "retry_count": 3, "max_retries": 3 }
  }
}
```

#### 大文件上传方案（>5MB）

当前 MVP 阶段使用直传模式（≤20MB），未来规模化时采用以下方案：

**方案：OSS 直传 + STS 临时凭证**

```
前端                        后端                        阿里云 OSS
  │                          │                            │
  │  1. GET /student/material/upload-token                │
  │  ────────────────► │                            │
  │                        │  2. 生成 STS 临时凭证       │
  │  ◄──────────────── │                            │
  │  { sts_token, bucket,  │                            │
  │    upload_key, expires }│                            │
  │                          │                            │
  │  3. 直传文件到 OSS（分片上传）                        │
  │  ──────────────────────────────────────────────►│
  │                          │                            │
  │  4. POST /student/material/upload-complete            │
  │  ────────────────► │                            │
  │                        │  5. 验证 OSS 文件存在       │
  │                        │  ──────────────────────────►│
  │                        │  6. 创建 study_uploads 记录  │
  │                        │  7. 触发 OCR 任务           │
  │  ◄──────────────── │                            │
  │  { resource_id, poll_url }                           │
```

**分片上传规则：**
- 文件 ≤5MB：直接上传，不分片
- 文件 5-20MB：分片大小 2MB
- 分片上传超时：单片 30s，整体 5min

**秒传机制（MVP 暂不实现，预留扩展）：**
```
前端在上传前计算文件 SHA256：
1. POST /student/material/check-duplicate { file_hash: "sha256..." }
2. 若 file_hash 已存在 → 返回 { duplicate: true, upload_id: 123 }
3. 若不存在 → 返回 { duplicate: false }，继续正常上传
```

**断点续传：**
- 利用 OSS 分片上传的 uploadId 实现
- 前端缓存 uploadId + 已完成分片列表到 localStorage
- 重新上传时先查询已完成分片，仅上传缺失部分

---

### 6.4 实时答疑（流式）

#### `POST /student/qa/chat/stream`

**请求体：**
```json
{
  "session_id": null,
  "message": "这道函数定义域的题我不会，能帮我讲讲吗？",
  "attachments": [
    { "type": "image", "upload_id": 456 }
  ],
  "subject_id": 2
}
```

**会话自动创建逻辑（`session_id=null` 时）：**

当请求中 `session_id` 为 `null` 时，后端自动执行以下逻辑：

1. **检查活跃会话**：查询当前学生是否存在 `status='active'` 的会话
   - 若存在且最后消息时间 <30 分钟 → 复用该会话（返回其 session_id）
   - 若存在但已超时 → 关闭旧会话，创建新会话
   - 若不存在 → 创建新会话

2. **创建新会话**：
   ```json
   {
     "student_id": "<当前用户>",
     "session_date": "<当前日期>",
     "subject_id": "<请求中的 subject_id，可空>",
     "status": "active"
   }
   ```

3. **SSE 流首事件**：新创建会话时，流的第一个事件为会话信息：
   ```
   data: {"type":"session_created","session_id":123}
   ```
   前端收到后应缓存 `session_id`，后续追问时携带。

4. **并发控制**：同一学生同时只允许 1 个 active 会话。

**追问场景**：`session_id` 非空时，直接在指定会话中追加消息，不检查/创建新会话。若指定会话已关闭，返回 `QA_SESSION_CLOSED` 错误。

**SSE 响应流：**
```
data: {"type":"chunk","content":"好的，我来帮你分析这道题。"}

data: {"type":"chunk","content":"题目要求求 $f(x) = \\sqrt{x-1}$ 的定义域。"}

data: {"type":"chunk","content":"首先，根号下的表达式必须 ≥ 0，"}

data: {"type":"chunk","content":"所以我们需要解不等式 $x-1 \\geq 0$。"}

data: {"type":"chunk","content":"你能告诉我，这个不等式应该怎么解呢？"}

data: {"type":"knowledge_points","data":[{"id":42,"name":"函数的定义域"},{"id":38,"name":"不等式基础"}]}

data: {"type":"strategy","data":"hint"}

data: [DONE]
```

**前端处理逻辑（TypeScript）：**
```typescript
async function streamChat(request: ChatRequest): Promise<void> {
  const response = await fetch("/api/v1/student/qa/chat/stream", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
    },
    body: JSON.stringify(request),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split("\n");

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6);
      if (payload === "[DONE]") return;

      const event: SseEvent = JSON.parse(payload);
      if (event.type === "chunk") {
        appendToMessage(event.content);
      } else if (event.type === "knowledge_points") {
        setKnowledgePoints(event.data);
      } else if (event.type === "strategy") {
        setStrategy(event.data);
      } else if (event.type === "error") {
        handleError(event.code, event.message);
      }
    }
  }
}
```

---

### 6.5 错题本

#### `GET /student/errors`

**请求参数示例：**
```
GET /student/errors?subject_id=2&is_recalled=false&page=1&page_size=20
```

**成功响应 `200`：**
```json
{
  "data": {
    "items": [
      {
        "id": 88,
        "subject_id": 2,
        "subject_name": "数学",
        "question_content": {
          "text": "设函数 $f(x) = \\sqrt{x-1}$，求其定义域。",
          "latex_expressions": ["\\sqrt{x-1}"]
        },
        "knowledge_points": [
          { "id": 42, "name": "函数的定义域" }
        ],
        "error_type": "concept_unclear",
        "entry_reason": "wrong",
        "is_explained": true,
        "is_recalled": false,
        "last_recall_at": null,
        "last_recall_result": null,
        "recall_count": 0,
        "created_at": "2026-03-16T20:30:00+08:00"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 43,
    "total_pages": 3
  }
}
```

#### `GET /student/errors/summary`

**成功响应 `200`：**
```json
{
  "data": {
    "total": 43,
    "unrecalled": 31,
    "by_subject": [
      { "subject_id": 2, "subject_name": "数学", "count": 18, "unrecalled": 13 },
      { "subject_id": 4, "subject_name": "物理", "count": 15, "unrecalled": 11 },
      { "subject_id": 5, "subject_name": "化学", "count": 10, "unrecalled": 7 }
    ],
    "by_error_type": {
      "calc_error": 12,
      "concept_unclear": 20,
      "careless": 6,
      "unknown": 5
    }
  }
}
```

#### `POST /student/errors/batch-recall`

**请求体：**
```json
{
  "error_ids": [88, 92, 95]
}
```

**成功响应 `200`：**
```json
{
  "data": {
    "scheduled_count": 3,
    "error_ids": [88, 92, 95]
  }
}
```

---

### 6.6 知识点状态

#### `GET /student/knowledge/status`

**请求参数示例：**
```
GET /student/knowledge/status?subject_id=2&status=反复失误&min_importance=0.6
```

**成功响应 `200`：**
```json
{
  "data": {
    "total": 195,
    "by_status": {
      "未观察": 90,
      "初步接触": 42,
      "需要巩固": 33,
      "基本掌握": 24,
      "反复失误": 6
    },
    "items": [
      {
        "knowledge_point_id": 42,
        "knowledge_point_name": "函数的定义域",
        "subject_name": "数学",
        "level": 3,
        "status": "反复失误",
        "importance_score": 0.80,
        "last_updated_at": "2026-03-18T19:45:00+08:00",
        "is_manual_corrected": false
      }
    ]
  }
}
```

### 6.7 学生端生成分享链接

#### `POST /student/report/share`

学生可从自己的周报页生成分享链接（权限矩阵 §6 学生对"生成分享链接"有 ✅ 权限）。
生成的链接内容与家长端生成的一致，均通过 `SHARE_OMIT_FIELDS` 过滤敏感字段。

**请求体：**
```json
{
  "week": "2026-W11",
  "expires_in_days": 7
}
```

**成功响应 `200`：**
```json
{
  "data": {
    "share_url": "https://api.studypilot.example.com/api/v1/share/eyJhbGciOiJIUzI1NiJ9...",
    "expires_at": "2026-03-25T23:59:59+08:00",
    "share_token": "eyJhbGciOiJIUzI1NiJ9..."
  }
}
```

> 生成的分享内容同 §8，不包含排名、原始图片、完整问答记录。

---

## 7. 家长端 API 契约

### 7.1 家长周报

#### `GET /parent/report/weekly?week=2026-W11`

**成功响应 `200`：**
```json
{
  "data": {
    "report_week": "2026-W11",
    "student_name": "小明",
    "usage_days": 5,
    "total_minutes": 430,
    "task_completion_rate": 0.82,
    "subject_risks": [
      { "subject_id": 2, "subject_name": "数学", "risk_level": "轻度风险", "effective_week": "2026-W11" },
      { "subject_id": 4, "subject_name": "物理", "risk_level": "中度风险", "effective_week": "2026-W11" },
      { "subject_id": 1, "subject_name": "语文", "risk_level": "稳定", "effective_week": "2026-W11" },
      { "subject_id": 3, "subject_name": "英语", "risk_level": "稳定", "effective_week": "2026-W11" },
      { "subject_id": 5, "subject_name": "化学", "risk_level": "轻度风险", "effective_week": "2026-W11" }
    ],
    "trend_description": "本周整体学习较稳定，物理有退步趋势，建议重点关注",
    "action_suggestions": [
      "鼓励孩子加强物理练习，特别是力学部分",
      "本周数学错题较多，可询问是否需要额外辅导"
    ],
    "class_rank": 12,
    "grade_rank": 45,
    "share_token": null
  }
}
```

> **注意**：家长视图不包含具体错题内容（`question_content`）、原始图片 URL 和完整问答记录，符合 PRD 隐私要求。

### 7.2 生成分享链接

#### `POST /parent/report/share`

**请求体：**
```json
{
  "week": "2026-W11",
  "expires_in_days": 7
}
```

**成功响应 `200`：**
```json
{
  "data": {
    "share_url": "https://api.studypilot.example.com/api/v1/share/eyJhbGciOiJIUzI1NiJ9.eyJzdHVkZW50X2lkIjozLCJyZXBvcnRfd2VlayI6IjIwMjYtVzExIiwiZXhwIjoxNzQzMzQyNDAwfQ.abc123",
    "expires_at": "2026-03-25T23:59:59+08:00",
    "share_token": "eyJhbGciOiJIUzI1NiJ9..."
  }
}
```

---

## 8. 分享链接 API 契约

### `GET /share/{token}`

**请求：** 无需 Authorization 头，Token 在路径中。

**成功响应 `200`：**
```json
{
  "data": {
    "student_name": "小明",
    "report_week": "2026-W11",
    "usage_days": 5,
    "total_minutes": 430,
    "trend_overview": "本周学习积极，物理有所进步，整体向好",
    "subject_risk_overview": [
      { "subject_name": "数学", "risk_level": "轻度风险" },
      { "subject_name": "物理", "risk_level": "中度风险" },
      { "subject_name": "语文", "risk_level": "稳定" }
    ],
    "next_stage_suggestions_summary": "建议下周重点巩固物理力学，并保持数学日常练习",
    "expires_at": "2026-03-25T23:59:59+08:00"
  }
}
```

**隐私保护确认**：分享内容**不包含**以下字段（由 `SHARE_OMIT_FIELDS` 在序列化层过滤）：

| 字段 | 归属 | 原因 |
|------|------|------|
| `class_rank` / `grade_rank` | student_profiles | 涉及隐私比较 |
| `original_images` (OSS URL) | study_uploads | 原始材料不对外 |
| `full_qa_history` | qa_sessions | 完整对话记录 |
| `structured_summary` | qa_sessions | 内部评估数据 |
| `admin_notes` | manual_corrections | 运营内部数据 |
| `content_hash` | error_book | 系统内部字段 |

**错误响应 `401`（过期）：**
```json
{
  "error": {
    "code": "AUTH_SHARE_TOKEN_EXPIRED",
    "message": "该分享链接已过期，请联系分享者重新生成",
    "detail": { "expired_at": "2026-03-18T00:00:00+08:00" }
  }
}
```

---

## 9. 管理端 API 契约

### 9.1 运行模式切换

#### `GET /admin/system/mode`

**成功响应 `200`：**
```json
{
  "data": {
    "current_mode": "normal",
    "switched_at": "2026-03-15T10:00:00+08:00",
    "switched_by": "admin"
  }
}
```

> **实现说明**：从 Redis key `system:run_mode` 读取，所有进程（API/Worker/Beat）共享，无需重启生效。

#### `POST /admin/system/mode`

**请求体：**
```json
{
  "mode": "best",
  "reason": "本周末考试，临时切换最优效果"
}
```

**成功响应 `200`：**
```json
{
  "data": {
    "previous_mode": "normal",
    "current_mode": "best",
    "switched_at": "2026-03-18T20:00:00+08:00"
  }
}
```

### 9.2 人工纠偏

#### `GET /admin/corrections/pending`

**请求参数：**
```
GET /admin/corrections/pending?target_type=ocr&page=1&page_size=20
```

**成功响应 `200`：**
```json
{
  "data": {
    "items": [
      {
        "id": 31,
        "target_type": "ocr",
        "target_id": 456,
        "status": "pending",
        "created_at": "2026-03-18T17:30:00+08:00"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 3,
    "total_pages": 1
  }
}
```

#### `POST /admin/corrections/ocr`

**请求体：**
```json
{
  "upload_id": 456,
  "corrected_content": {
    "extracted_questions": [
      {
        "question_text": "设函数 $f(x) = \\sqrt{x-1}$，求其定义域。",
        "latex_expressions": ["\\sqrt{x-1}"],
        "question_type": "解答题"
      }
    ],
    "subject_detected": "数学",
    "knowledge_points": [
      { "id": 42, "name": "函数的定义域", "confidence": 1.0 }
    ]
  },
  "correction_reason": "原 OCR 识别将根号符号解析错误，手动修正"
}
```

**成功响应 `200`：**
```json
{
  "data": {
    "correction_id": 31,
    "target_type": "ocr",
    "target_id": 456,
    "success": true,
    "message": "OCR 结果已修正，upload_id=456 已标记为人工纠偏"
  }
}
```

#### `POST /admin/corrections/knowledge`

**请求体：**
```json
{
  "student_id": 3,
  "knowledge_point_id": 42,
  "new_status": "基本掌握",
  "correction_reason": "学生线下已掌握，系统状态滞后"
}
```

**成功响应 `200`：**
```json
{
  "data": {
    "correction_id": 32,
    "target_type": "knowledge",
    "target_id": 42,
    "success": true,
    "message": "知识点状态已修正为「基本掌握」，is_manual_corrected=true"
  }
}
```

### 9.3 系统监控

#### `GET /admin/metrics/today`

**成功响应 `200`：**
```json
{
  "data": {
    "date": "2026-03-18",
    "active_users": 3,
    "plans_generated": 3,
    "uploads_count": 7,
    "qa_sessions": 5,
    "total_api_requests": 248,
    "api_error_rate": 0.008,
    "current_mode": "normal",
    "estimated_cost_today": 12.50,
    "pending_corrections": 2
  }
}
```

#### `GET /admin/metrics/model-calls?date=2026-03-18`

**成功响应 `200`：**
```json
{
  "data": {
    "date": "2026-03-18",
    "by_agent": [
      {
        "agent_name": "tutoring",
        "total_calls": 42,
        "success_calls": 41,
        "fallback_calls": 1,
        "avg_latency_ms": 3200,
        "p95_latency_ms": 8500,
        "total_input_tokens": 124800,
        "total_output_tokens": 89600,
        "estimated_cost": 8.20
      },
      {
        "agent_name": "extraction",
        "total_calls": 7,
        "success_calls": 6,
        "fallback_calls": 1,
        "avg_latency_ms": 4100,
        "p95_latency_ms": 9200,
        "total_input_tokens": 21000,
        "total_output_tokens": 8400,
        "estimated_cost": 2.10
      },
      {
        "agent_name": "planning",
        "total_calls": 3,
        "success_calls": 3,
        "fallback_calls": 0,
        "avg_latency_ms": 5800,
        "p95_latency_ms": 7100,
        "total_input_tokens": 18000,
        "total_output_tokens": 12000,
        "estimated_cost": 1.80
      }
    ]
  }
}
```

#### `GET /admin/metrics/health`

**正常响应 `200`：**
```json
{
  "data": {
    "status": "healthy",
    "components": {
      "database": "ok",
      "redis": "ok",
      "celery_worker": "ok",
      "oss": "ok"
    }
  }
}
```

**降级响应 `200`（Redis 不可用）：**
```json
{
  "data": {
    "status": "degraded",
    "components": {
      "database": "ok",
      "redis": "error",
      "celery_worker": "ok",
      "oss": "ok"
    }
  }
}
```

---

## 10. 版本管理策略

### 10.1 版本号规则

当前版本：`v1`，路径前缀 `/api/v1`。

版本号仅在**破坏性变更**时递增：

| 变更类型 | 是否递增版本 | 示例 |
|---------|------------|------|
| 新增接口 | ❌ 不递增 | 增加 `/student/errors/summary` |
| 新增可选请求字段 | ❌ 不递增 | 新增可选 query param |
| 新增响应字段 | ❌ 不递增 | 响应体增加 `warning` 字段 |
| 修改字段类型/含义 | ✅ 递增 | `status` 值集合变化 |
| 删除/重命名字段 | ✅ 递增 | 删除 `is_history_inferred` |
| 修改 URL 路径 | ✅ 递增 | 路径结构变化 |
| 修改 HTTP 方法 | ✅ 递增 | GET 改为 POST |

### 10.2 向前兼容性原则

**服务端承诺**：
1. **新增字段**：响应体中新增字段，前端应忽略未知字段（不报错）
2. **枚举扩展**：枚举字段可能增加新值，前端应有 `default` 兜底处理
3. **可选字段**：新增的请求参数均为可选，不影响现有请求
4. **字段顺序**：JSON 字段顺序不保证稳定，前端不应依赖顺序

**前端处理规范（TypeScript）**：
```typescript
// ✅ 正确：为枚举字段提供兜底
function getRiskBadgeColor(risk: RiskLevel | string): string {
  switch (risk) {
    case "稳定": return "green";
    case "轻度风险": return "yellow";
    case "中度风险": return "orange";
    case "高风险": return "red";
    default: return "gray";   // 新枚举值的兜底
  }
}

// ✅ 正确：可选字段加空值保护
const warning = plan.warning ?? null;

// ❌ 错误：假设特定字段顺序或依赖字段不存在
```

### 10.3 版本共存策略

MVP 阶段（≤5 用户，自用）：
- **仅维护 v1**，不做并行版本
- v1 接口不保证永久向前兼容（升级用户端代码即可）
- 破坏性变更前提前 1 周告知使用方

未来规模化时的升级策略（备忘）：
```
v1 维护期间：
  - /api/v1 继续服务
  - /api/v2 新版本上线
  - 至少维护 v1 六个月过渡期

过渡机制：
  - 响应头添加 Deprecation: true 标记即将废弃的接口
  - 过渡期日志记录 v1 调用量，待降至 0 后下线
```

### 10.4 API 变更日志（CHANGELOG）

破坏性变更和重要新增均应记录。格式模板：

```markdown
## [v1] 2026-03-18

### Added
- `GET /student/errors/summary` — 错题概要统计接口
- `POST /student/errors/batch-recall` — 批量召回接口
- `PATCH /student/plan/mode` — 学习模式切换接口

### Changed
- `POST /student/plan/generate` 响应新增可选字段 `warning`（generic_fallback 时有值）

### Breaking Changes
- 无
```

### 10.5 文档真值源策略

**当前状态**：系统同时维护 `api-openapi.yaml`（机器可读）和 `api-contract.md`（工程实现补充），内容存在重叠。

**真值源规则（自 v1 起执行）：**

| 内容类型 | 真值源 | 说明 |
|---------|--------|------|
| 端点路径、HTTP 方法、状态码 | `api-openapi.yaml` | 机器可读，可自动生成 Swagger UI |
| 请求/响应 JSON Schema | `api-openapi.yaml` | 与 Pydantic 模型保持同步 |
| TypeScript 类型定义 | `api-contract.md` §5 | 前端直接使用 |
| 完整 JSON 示例 | `api-contract.md` §6-9 | 开发参考和测试用例 |
| 错误码注册表 | `api-contract.md` §4 | 完整的错误码列表和前端处理建议 |
| 认证流程详细说明 | `api-contract.md` §2 | 包含流程图和实现细节 |
| 版本管理策略 | `api-contract.md` §10 | 策略性文档 |

**同步规则：**
1. 新增/修改端点时，**先更新 `api-openapi.yaml`**，再同步 `api-contract.md` 的示例和类型
2. `api-openapi.yaml` 中的 Schema 定义应与 `api-contract.md` §5 的 TypeScript 类型一一对应
3. 发现两者不一致时，以 `api-openapi.yaml` 为准（端点/Schema），以 `api-contract.md` 为准（业务规则/错误码）

**未来优化（MVP 后）：**
- 引入 `openapi-typescript` 工具从 YAML 自动生成 TypeScript 类型，替代手动维护
- 使用 `redocly` 合并 YAML + Markdown 生成统一文档站点

---

## 附录 A：接口速查表

### 学生端

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/auth/token-login` | 学生/家长登录 | 无 |
| POST | `/auth/refresh` | 刷新 Token | student/parent/admin |
| GET | `/student/profile` | 获取学生档案 | student |
| POST | `/student/profile` | 创建学生档案 | student |
| PATCH | `/student/profile` | 更新学生档案 | student |
| POST | `/student/onboarding/submit` | 提交入学问卷 | student |
| GET | `/student/onboarding/status` | 查询问卷状态 | student |
| POST | `/student/plan/generate` | 生成今日计划 | student |
| GET | `/student/plan/today` | 获取今日计划 | student |
| PATCH | `/student/plan/mode` | 切换学习模式 | student |
| PATCH | `/student/plan/tasks/{id}` | 更新任务状态 | student |
| POST | `/student/material/upload` | 上传学习材料 | student |
| GET | `/student/material/list` | 上传历史列表 | student |
| GET | `/student/material/{id}/ocr-status` | OCR 状态轮询 | student |
| POST | `/student/material/{id}/retry-ocr` | 重试 OCR | student |
| POST | `/student/qa/chat` | 发送答疑消息 | student |
| POST | `/student/qa/chat/stream` | 流式答疑（SSE）| student |
| GET | `/student/qa/history` | 答疑历史列表 | student |
| GET | `/student/qa/sessions/{id}` | 会话详情 | student |
| GET | `/student/errors` | 错题列表 | student |
| GET | `/student/errors/summary` | 错题概要统计 | student |
| GET | `/student/errors/{id}` | 错题详情 | student |
| POST | `/student/errors/{id}/recall` | 触发单题召回 | student |
| POST | `/student/errors/batch-recall` | 批量召回 | student |
| GET | `/student/knowledge/status` | 知识点状态 | student |
| GET | `/student/report/weekly` | 周报（学生视角）| student |
| GET | `/student/report/weekly/summary` | 周报概览 | student |
| GET | `/config/textbook-versions` | 教材版本列表 | 无 |

### 家长端

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/auth/token-login` | 家长登录（role=parent）| 无 |
| GET | `/parent/report/weekly` | 周报（家长视角）| parent |
| GET | `/parent/report/stage` | 阶段性报告 | parent |
| POST | `/parent/report/share` | 生成分享链接 | parent |
| GET | `/parent/profile/risk` | 学科风险概览 | parent |
| GET | `/parent/profile/trend` | 趋势数据 | parent |
| POST | `/parent/profile/supplement` | 补录基础信息 | parent |
| POST | `/parent/exam/record` | 补录考试成绩 | parent |

### 分享端

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | `/share/{token}` | 获取脱敏摘要 | JWT路径参数 |
| GET | `/share/{token}/validate` | 验证链接有效性 | JWT路径参数 |

### 管理端

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/auth/admin-login` | 管理员登录 | 无 |
| GET | `/admin/system/mode` | 获取运行模式 | admin |
| POST | `/admin/system/mode` | 切换运行模式 | admin |
| GET | `/admin/corrections/pending` | 待处理纠偏列表 | admin |
| GET | `/admin/corrections/logs` | 历史纠偏记录 | admin |
| GET | `/admin/corrections/{id}` | 纠偏项详情 | admin |
| POST | `/admin/corrections/ocr` | 修正 OCR 结果 | admin |
| POST | `/admin/corrections/knowledge` | 修正知识点标注 | admin |
| POST | `/admin/corrections/plan` | 调整学习计划 | admin |
| GET | `/admin/metrics/today` | 今日概览 | admin |
| GET | `/admin/metrics/health` | 系统健康状态 | admin |
| GET | `/admin/metrics/model-calls` | 模型调用统计 | admin |
| GET | `/admin/metrics/costs` | 成本统计 | admin |
| GET | `/admin/metrics/errors` | 错误统计 | admin |
| GET | `/admin/metrics/fallbacks` | 降级统计 | admin |
| GET | `/admin/metrics/latency` | 延迟统计 | admin |

---

## 附录 B：后端 Pydantic 模型对照

OpenAPI YAML (`docs/api-openapi.yaml`) 中的 Schema 与后端 Pydantic V2 模型的对应关系：

```
api-openapi.yaml Schema     →   后端 Pydantic 模型位置
─────────────────────────────────────────────────────
DailyPlan                   →   app/schemas/plan.py:DailyPlanResponse
PlanTask                    →   app/schemas/plan.py:PlanTaskResponse
OcrStatusResponse           →   app/schemas/upload.py:OcrStatusResponse
ChatRequest                 →   app/schemas/qa.py:ChatRequest
ChatResponse                →   app/schemas/qa.py:ChatResponse
ErrorBookItem               →   app/schemas/error_book.py:ErrorBookItemResponse
WeeklyReportStudent         →   app/schemas/report.py:WeeklyReportStudentResponse
WeeklyReportParent          →   app/schemas/report.py:WeeklyReportParentResponse
ShareContent                →   app/schemas/share.py:ShareContentResponse
OnboardingSubmitRequest     →   app/schemas/onboarding.py:OnboardingSubmitRequest
StructuredSummary           →   app/schemas/assessment.py:StructuredSummary
```

所有 Response Schema 均应包含 `model_config = ConfigDict(from_attributes=True)` 以支持从 ORM 对象直接序列化。
