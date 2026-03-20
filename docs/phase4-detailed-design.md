# Phase 4 详细设计：前后端联调

> 状态：待实施
> 创建日期：2026-03-20

## 1. 目标与范围

将前端 14 个页面从 Mock 数据模式切换为真实 API 调用，实现完整的端到端功能闭环。

**范围边界**：
- 本阶段只做联调，不新增后端 API 端点或前端页面
- 后端已完成：Phase 1（基础设施）+ Phase 2（P0 API）+ Phase 3（LLM Agent 集成）
- 前端已完成：14 个路由页面 + 9 个 UI 组件 + TypeScript 类型定义 + API 客户端 + SSE 流工具

**交付物**：
1. 所有页面使用真实 API 数据
2. 后端 CORS 中间件
3. 认证流程端到端打通（登录 → token 存储 → 自动携带 → 401 跳转）
4. SSE 流式答疑接入
5. OCR 状态轮询
6. 前端错误处理与 loading 状态

---

## 2. 现状分析

### 2.1 后端 API 路由表

所有路由前缀 `/api/v1`：

| 模块 | 前缀 | 端点数 |
|------|------|--------|
| auth | `/auth` | 4（token-login, admin-login, me, refresh） |
| student_profile | `/student` | 5（profile CRUD, onboarding submit/status） |
| plan | `/student/plan` | 4（generate, today, mode, tasks/{id}） |
| upload | `/student/material` | 4（upload, list, ocr-status, retry-ocr） |
| qa | `/student/qa` | 4（chat, chat/stream, history, sessions/{id}） |
| error_book | `/student/errors` | 5（list, summary, detail, recall, batch-recall） |
| knowledge | `/student/knowledge` | 1（status） |
| report | `/student/report` | 3（weekly, weekly/summary, share） |
| share | `/share` | 2（{token}, {token}/validate） |
| parent | `/parent` | 6（report/weekly, report/share, profile/risk, profile/trend, profile/supplement, exam/record） |
| admin | `/admin` | 6（system/mode GET/POST, corrections/pending, corrections/ocr, corrections/knowledge, metrics/today, metrics/health, metrics/model-calls） |
| config | `/config` | 1（textbook-versions） |

### 2.2 前端 API 基础设施（已就绪）

| 文件 | 功能 | 状态 |
|------|------|------|
| `src/lib/api.ts` | fetch 封装，Bearer token 自动注入，JSON/FormData 支持，ApiError 类 | ✅ 可用 |
| `src/lib/stream.ts` | SSE 流处理，支持 POST + Auth header，[DONE] 终止符 | ✅ 可用 |
| `src/lib/env.ts` | `NEXT_PUBLIC_API_BASE` 环境变量（默认 `http://localhost:8000/api/v1`） | ✅ 可用 |
| `src/types/api.ts` | 完整 TypeScript 类型定义（297 行），与后端 schema 对齐 | ✅ 可用 |
| `src/lib/mock-data.ts` | Mock 数据（224 行），所有页面依赖此文件 | 🔄 待替换 |

### 2.3 前端当前问题

1. **所有页面直接导入 mock-data.ts** — 无真实 API 调用
2. **登录完全 mock** — `setTimeout(800ms)` + 硬编码 `mock_token` 存入 localStorage
3. **入学问卷未对接 API** — 表单提交只写 localStorage
4. **无 CORS 中间件** — 后端 `main.py` 未配置 CORSMiddleware
5. **无 401 自动跳转** — API 客户端不处理认证过期
6. **无数据刷新机制** — 未使用 SWR（已安装但未集成）
7. **loading 用 setTimeout 模拟** — 不反映真实请求耗时

---

## 3. 架构设计

### 3.1 数据获取策略

采用 **SWR（stale-while-revalidate）** 作为数据获取层，已在 `package.json` 中安装。

新增文件：`src/lib/hooks.ts` — 封装所有 API 调用为 custom hooks。

```typescript
// src/lib/hooks.ts 设计

// 通用 fetcher
const fetcher = <T>(path: string) => api.get<T>(path);

// 示例 hook
export function useDailyPlan() {
  return useSWR<DailyPlan | null>("/student/plan/today", fetcher);
}

export function useErrorSummary() {
  return useSWR<ErrorSummary>("/student/errors/summary", fetcher);
}
```

**设计决策**：
- **GET 请求** → SWR hook（自动缓存、重新验证、loading/error 状态）
- **POST/PATCH/DELETE** → 直接调用 `api.post()` / `api.patch()` + `mutate()` 刷新关联缓存
- **SSE 流** → 直接使用 `streamRequest()`，不走 SWR

### 3.2 认证流程

```
登录页                         API 客户端                         后端
  │                              │                               │
  │─── POST /auth/token-login ──→│──────────────────────────────→│
  │                              │←── { access_token, user } ────│
  │←── 存储 token + user info ───│                               │
  │                              │                               │
  │─── 后续请求 ────────────────→│── Authorization: Bearer xxx ─→│
  │                              │                               │
  │                              │←── 401 Unauthorized ──────────│
  │←── 自动跳转 /login ─────────│                               │
```

**token 存储方案**（保持现有 localStorage 方案，MVP 阶段足够）：
- `access_token` — JWT token
- `user_role` — "student" | "parent" | "admin"
- `user_name` — 显示名称
- `student_id` — 学生 ID（家长端需要）
- `onboarding_completed` — 入学问卷状态

### 3.3 SSE 流式答疑集成

```
QA 页面                    streamRequest()              后端 SSE
  │                              │                        │
  │── POST /student/qa/chat/stream →                      │
  │                              │── fetch(POST, auth) ──→│
  │                              │←── data: {"type":"chunk","content":"..."} ──│
  │←── onMessage(chunk) ────────│                         │
  │── 更新 messages state ──────│                         │
  │                              │←── data: {"type":"knowledge_points",...} ───│
  │←── onMessage(kp) ──────────│                         │
  │                              │←── data: {"type":"strategy",...} ───────────│
  │←── onMessage(strategy) ────│                         │
  │                              │←── data: [DONE] ───────│
  │←── onDone() ────────────────│                         │
```

SSE 事件类型（与后端 `services/qa.py` 对齐）：
1. `{"type": "chunk", "content": "..."}` — 文本片段，逐步追加到 assistant 消息
2. `{"type": "knowledge_points", "data": [...]}` — 知识点列表，流结束后展示
3. `{"type": "strategy", "data": "hint"}` — 教学策略标签
4. `[DONE]` — 流结束信号

### 3.4 OCR 状态轮询

```
上传页面                      API                         后端
  │                            │                            │
  │── POST /student/material/upload (FormData) ────────────→│
  │←── { id, ocr_status: "pending" } ──────────────────────│
  │                            │                            │
  │── [轮询] GET /student/material/{id}/ocr-status ────────→│
  │←── { ocr_status: "processing" } ──────────────────────│
  │── [3s 后] GET /student/material/{id}/ocr-status ──────→│
  │←── { ocr_status: "completed", ocr_result: {...} } ────│
  │── 停止轮询，更新 UI ──────│                            │
```

轮询策略：
- 间隔：3 秒
- 最大次数：60（3 分钟超时）
- 终止条件：`ocr_status` 为 `completed` 或 `failed`

### 3.5 错误处理策略

在 `api.ts` 中增强全局错误处理：

| HTTP 状态码 | 处理方式 |
|-------------|----------|
| 401 | 清除 localStorage，跳转 `/login`，Toast "登录已过期" |
| 403 | Toast "没有权限执行此操作" |
| 404 | 组件级处理（如"会话不存在"） |
| 409 | 组件级处理（如"入学问卷已完成"） |
| 422 | 表单验证错误，Toast 具体字段提示 |
| 500 | Toast "服务器错误，请稍后重试" |
| 网络错误 | Toast "网络连接失败，请检查网络" |

---

## 4. 后端变更

### 4.1 CORS 中间件

**修改文件**：`server/app/main.py`

```python
from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:
    application = FastAPI(title="StudyPilot API", version="0.1.0")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # ... 其余不变
```

**修改文件**：`server/app/core/config.py`

新增配置项：
```python
CORS_ORIGINS: list[str] = ["http://localhost:3000"]
```

### 4.2 PaginatedResponse 前端兼容

当前后端 `PaginatedResponse` 结构为 `{ data: { items, page, page_size, total, total_pages } }`。

前端 `api.get()` 自动提取 `.data`，所以分页接口返回的是 `{ items, page, ... }` 对象。

需要在 `src/lib/api.ts` 中新增分页请求方法：

```typescript
export const api = {
  // ... 现有方法
  getPaginated: <T>(path: string) =>
    request<{ items: T[]; page: number; page_size: number; total: number; total_pages: number }>(path),
};
```

---

## 5. 前端变更清单

### 5.1 新增文件（2 个）

| 文件 | 功能 |
|------|------|
| `src/lib/hooks.ts` | SWR custom hooks，封装所有 GET API 调用 |
| `src/lib/auth.ts` | 认证工具函数（login, logout, getUser, isAuthenticated） |

### 5.2 修改文件（16 个）

| 文件 | 变更内容 |
|------|----------|
| `src/lib/api.ts` | 增加 401 自动跳转、getPaginated 方法 |
| `src/app/page.tsx` | 用 `/auth/me` 验证 token 有效性，替代 localStorage 检查 |
| `src/app/login/page.tsx` | 对接 `/auth/token-login` 和 `/auth/admin-login` |
| `src/app/onboarding/page.tsx` | 对接 `/student/onboarding/submit`，从 `/auth/me` 获取状态 |
| `src/app/dashboard/page.tsx` | SWR hooks 替换 5 个 mock 数据源 |
| `src/app/plan/today/page.tsx` | SWR + PATCH `/student/plan/tasks/{id}` |
| `src/app/upload/page.tsx` | FormData 上传 + OCR 轮询 + SWR 上传历史 |
| `src/app/qa/page.tsx` | SSE 流式集成 + SWR 历史 + POST 创建消息 |
| `src/app/errors/page.tsx` | SWR 分页 + 筛选 + POST recall |
| `src/app/report/weekly/page.tsx` | SWR 周报数据 |
| `src/app/parent/report/weekly/page.tsx` | SWR 家长周报 |
| `src/app/share/[token]/page.tsx` | GET `/share/{token}` + validate |
| `src/app/admin/dashboard/page.tsx` | SWR 指标 + 纠偏列表 |
| `src/app/admin/corrections/page.tsx` | SWR 分页 + POST 处理纠偏 |
| `src/app/admin/metrics/page.tsx` | SWR 详细指标 |
| `src/components/layout/app-header.tsx` | 从 localStorage 读取真实用户信息 + 模式切换 API |

### 5.3 可删除文件（1 个）

| 文件 | 原因 |
|------|------|
| `src/lib/mock-data.ts` | 所有页面切换到真实 API 后不再需要 |

---

## 6. 逐页面联调设计

### 6.1 登录页 `/login`

**当前**：`setTimeout(800ms)` + 硬编码 mock_token

**改造**：

```typescript
// 学生/家长登录
const res = await api.post<AuthResponse>("/auth/token-login", {
  token: token,
  login_type: role,  // "student" | "parent"
});

// 管理员登录
const res = await api.post<AuthResponse>("/auth/admin-login", {
  phone: username,
  password: password,
});

// 存储
localStorage.setItem("access_token", res.access_token);
localStorage.setItem("user_role", res.user.role);
localStorage.setItem("user_name", res.user.nickname);
if (res.user.student_id) {
  localStorage.setItem("student_id", String(res.user.student_id));
}
```

**错误处理**：
- `INVALID_TOKEN` → "登录令牌无效，请联系管理员"
- `INVALID_CREDENTIALS` → "用户名或密码错误"

### 6.2 入学问卷 `/onboarding`

**当前**：表单提交仅写 localStorage

**改造**：

```typescript
async function handleSubmit() {
  const subjects = [...REQUIRED_SUBJECTS, ...electives];
  await api.post("/student/onboarding/submit", {
    grade,
    textbook_version: textbookVersion,
    class_rank: classRank ? parseInt(classRank) : undefined,
    grade_rank: gradeRank ? parseInt(gradeRank) : undefined,
    class_total: classTotal ? parseInt(classTotal) : undefined,
    grade_total: gradeTotal ? parseInt(gradeTotal) : undefined,
    subject_combination: subjects,
    exam_schedules: exams.filter(e => e.exam_date),
  });
  localStorage.removeItem("onboarding_draft");
  localStorage.setItem("onboarding_completed", "true");
  router.push("/dashboard");
}
```

**进入页面时检查**：调用 `GET /student/onboarding/status` 判断是否已完成。

### 6.3 仪表板 `/dashboard`

**当前**：导入 5 个 mock 数据

**改造**（使用 SWR hooks）：

```typescript
const { data: plan, isLoading: planLoading } = useDailyPlan();
const { data: uploads } = useRecentUploads();
const { data: qaHistory } = useQAHistory();
const { data: errorSummary } = useErrorSummary();
const { data: weeklyReport } = useWeeklyReport();

const loading = planLoading; // 主要数据加载完即可展示
```

**API 映射**：
| Mock 数据 | API 路径 |
|-----------|----------|
| `mockDailyPlan` | `GET /student/plan/today` |
| `mockRecentUploads` | `GET /student/material/list?page=1&page_size=3` |
| `mockQAHistory` | `GET /student/qa/history?page=1&page_size=3` |
| `mockErrorSummary` | `GET /student/errors/summary` |
| `mockWeeklyReport` | `GET /student/report/weekly` |

**空数据处理**：
- 无今日计划 → 显示"点击生成今日计划"按钮 → `POST /student/plan/generate`
- 无上传历史 → 正常展示上传入口
- 无周报 → 隐藏周报概况栏

### 6.4 今日计划 `/plan/today`

**当前**：`mockDailyPlan` + 本地 state 更新

**改造**：

```typescript
const { data: plan, mutate } = useDailyPlan();

async function updateTaskStatus(taskId: number, status: TaskStatus) {
  await api.patch<PlanTask>(`/student/plan/tasks/${taskId}`, { status });
  mutate(); // 刷新计划数据
  if (status === "completed") toast("任务已完成", "success");
}
```

**计划不存在时**：显示生成按钮 → `POST /student/plan/generate` → `mutate()`

### 6.5 上传页 `/upload`

**当前**：`setTimeout` 模拟 OCR

**改造**：

```typescript
async function handleUpload() {
  const formData = new FormData();
  formData.append("upload_type", selectedType);
  if (selectedSubject) formData.append("subject_id", getSubjectId(selectedSubject).toString());
  if (note) formData.append("note", note);

  if (inputMode === "photo") {
    // 需要将 File 对象保留在 images state 中
    for (const img of imageFiles) {
      formData.append("file", img);
    }
  } else {
    formData.append("text_content", textContent);
  }

  const result = await api.post<StudyUpload>("/student/material/upload", formData);

  // 开始 OCR 轮询
  if (result.ocr_status === "pending" || result.ocr_status === "processing") {
    pollOcrStatus(result.id);
  }
}

async function pollOcrStatus(uploadId: number) {
  let attempts = 0;
  const interval = setInterval(async () => {
    attempts++;
    const status = await api.get<{ ocr_status: OcrStatus }>(`/student/material/${uploadId}/ocr-status`);
    updateImageStatus(uploadId, status.ocr_status);

    if (status.ocr_status === "completed" || status.ocr_status === "failed" || attempts >= 60) {
      clearInterval(interval);
      if (status.ocr_status === "completed") toast("识别完成", "success");
      if (status.ocr_status === "failed") toast("识别失败，可稍后重试", "error");
    }
  }, 3000);
}
```

**上传历史**：`useUploadHistory()` SWR hook → `GET /student/material/list`

**重要改动**：images state 需要同时保留 `File` 对象（用于 FormData 提交）和预览 URL。

```typescript
interface PreviewImage {
  id: string;
  file: File;          // 新增：保留原始 File
  url: string;         // 预览 URL（仍用 createObjectURL）
  ocrStatus: OcrStatus;
  uploadId?: number;   // 新增：上传后获得
}
```

### 6.6 答疑页 `/qa`

**当前**：`setTimeout` 模拟 + 硬编码回复

**改造**：

```typescript
const sendMessage = useCallback(async () => {
  if (!input.trim() || sending) return;

  const userMsg: QAMessage = {
    id: Date.now(),
    role: "user",
    content: input.trim(),
    created_at: new Date().toISOString(),
  };
  setMessages(prev => [...prev, userMsg]);
  setInput("");
  setSending(true);

  // 创建空的 assistant 消息占位
  const aiMsgId = Date.now() + 1;
  const aiMsg: QAMessage = {
    id: aiMsgId,
    role: "assistant",
    content: "",
    created_at: new Date().toISOString(),
  };
  setMessages(prev => [...prev, aiMsg]);
  setStreaming(true);
  setSending(false);

  await streamRequest("/student/qa/chat/stream", {
    method: "POST",
    body: {
      message: input.trim(),
      session_id: currentSessionId || undefined,
      subject_id: getSubjectId(subject),
    },
    onMessage: (data) => {
      try {
        const event = JSON.parse(data);
        if (event.type === "chunk") {
          setMessages(prev =>
            prev.map(m => m.id === aiMsgId
              ? { ...m, content: m.content + event.content }
              : m
            )
          );
        } else if (event.type === "knowledge_points") {
          setMessages(prev =>
            prev.map(m => m.id === aiMsgId
              ? { ...m, knowledge_points: event.data.map((kp: any) => kp.name || kp) }
              : m
            )
          );
        } else if (event.type === "strategy") {
          setMessages(prev =>
            prev.map(m => m.id === aiMsgId
              ? { ...m, tutoring_strategy: event.data }
              : m
            )
          );
        }
      } catch { /* ignore non-JSON lines */ }
    },
    onDone: () => setStreaming(false),
    onError: (err) => {
      setStreaming(false);
      toast("回复生成失败，请重试", "error");
    },
  });
}, [input, sending, currentSessionId, subject]);
```

**会话管理**：
- 首次发消息时 `session_id` 为空 → 后端创建新会话，从 SSE meta 事件获取 `session_id`
- 后续消息携带 `session_id`
- 历史会话列表：`useQAHistory()` → `GET /student/qa/history`
- 点击历史会话：`useSessionDetail(id)` → `GET /student/qa/sessions/{id}`

**注意**：后端 `POST /student/qa/chat/stream` 返回的是 `StreamingResponse`，不在 `SuccessResponse` 包装内。`streamRequest()` 直接读取 SSE 流。

### 6.7 错题本 `/errors`

**当前**：`mockErrors` + `mockErrorSummary`

**改造**：

```typescript
const [subjectFilter, setSubjectFilter] = useState<number | undefined>();
const [page, setPage] = useState(1);

const { data: summary } = useErrorSummary();
const { data: errors } = useErrorList({ subject_id: subjectFilter, page, page_size: 20 });

async function handleRecall(errorId: number) {
  await api.post(`/student/errors/${errorId}/recall`);
  mutateErrors();
  mutateSummary();
  toast("已标记为召回", "success");
}
```

### 6.8 周报 `/report/weekly`

**当前**：`mockWeeklyReport`

**改造**：

```typescript
const { data: report, isLoading } = useWeeklyReport();
```

分享功能：
```typescript
async function handleShare() {
  const result = await api.post<{ token: string; url: string }>("/student/report/share", {
    report_week: report.report_week,
  });
  // 显示分享链接
}
```

### 6.9 家长周报 `/parent/report/weekly`

**当前**：`mockParentReport`

**改造**：

```typescript
const { data: report, isLoading } = useParentWeeklyReport();
// GET /parent/report/weekly
```

### 6.10 分享页 `/share/[token]`

**当前**：`mockShareReport`

**改造**：

```typescript
// 此页面不需要认证
const { token } = useParams();
const { data: report, error, isLoading } = useSWR(
  token ? `/share/${token}` : null,
  (path) => api.get<ShareReport>(path)
);

// 错误处理
if (error?.code === "SHARE_EXPIRED") {
  return <ExpiredView />;
}
```

### 6.11 管理仪表板 `/admin/dashboard`

**当前**：`mockMetrics` + `mockCorrections`

**改造**：

```typescript
const { data: metrics } = useAdminMetrics();
const { data: corrections } = usePendingCorrections();
```

### 6.12 管理纠偏 `/admin/corrections`

**当前**：`mockCorrections` + 本地 state 过滤

**改造**：

```typescript
const { data, mutate } = usePendingCorrections({ page, status: filter });

async function handleResolve(id: number, correctedData: Record<string, unknown>) {
  await api.post("/admin/corrections/ocr", { correction_id: id, corrected_content: correctedData });
  mutate();
  toast("已处理", "success");
}
```

### 6.13 管理指标 `/admin/metrics`

**当前**：`mockMetrics`

**改造**：

```typescript
const { data: todayMetrics } = useSWR("/admin/metrics/today", fetcher);
const { data: healthMetrics } = useSWR("/admin/metrics/health", fetcher);
const { data: modelCalls } = useSWR("/admin/metrics/model-calls", fetcher);
```

### 6.14 AppHeader 模式切换

**当前**：纯本地 state

**改造**：

```typescript
async function onModeChange(mode: string) {
  // 仅管理员可切换系统模式
  await api.post("/admin/system/mode", { mode });
  setCurrentMode(mode);
}
```

对于学生端，模式切换调用 `PATCH /student/plan/mode`。

---

## 7. SWR Hooks 完整设计

```typescript
// src/lib/hooks.ts

import useSWR from "swr";
import { api } from "./api";
import type {
  DailyPlan, StudyUpload, QASession, QAMessage,
  ErrorBookItem, ErrorSummary, WeeklyReport,
  ParentWeeklyReport, ShareReport, SystemMetrics,
  CorrectionItem,
} from "@/types/api";

const fetcher = <T>(path: string) => api.get<T>(path);

// === 学生端 ===

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
    { refreshInterval: 3000 }  // 轮询
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
  return useSWR("/student/knowledge/status", fetcher);
}

export function useWeeklyReport() {
  return useSWR<WeeklyReport>("/student/report/weekly", fetcher);
}

export function useWeeklyReportSummary() {
  return useSWR("/student/report/weekly/summary", fetcher);
}

// === 家长端 ===

export function useParentWeeklyReport() {
  return useSWR<ParentWeeklyReport>("/parent/report/weekly", fetcher);
}

export function useParentRisk() {
  return useSWR("/parent/profile/risk", fetcher);
}

export function useParentTrend() {
  return useSWR("/parent/profile/trend", fetcher);
}

// === 管理端 ===

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
```

---

## 8. 认证工具模块设计

```typescript
// src/lib/auth.ts

import { api } from "./api";
import type { AuthResponse, AuthUser } from "@/types/api";

export interface StoredAuth {
  token: string;
  role: "student" | "parent" | "admin";
  userName: string;
  studentId: number | null;
}

export function getStoredAuth(): StoredAuth | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem("access_token");
  if (!token) return null;
  return {
    token,
    role: (localStorage.getItem("user_role") as StoredAuth["role"]) || "student",
    userName: localStorage.getItem("user_name") || "",
    studentId: localStorage.getItem("student_id")
      ? parseInt(localStorage.getItem("student_id")!)
      : null,
  };
}

export function saveAuth(res: AuthResponse): void {
  localStorage.setItem("access_token", res.access_token);
  localStorage.setItem("user_role", res.user.role);
  localStorage.setItem("user_name", res.user.nickname);
  if (res.user.student_id) {
    localStorage.setItem("student_id", String(res.user.student_id));
  }
}

export function clearAuth(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("user_role");
  localStorage.removeItem("user_name");
  localStorage.removeItem("student_id");
  localStorage.removeItem("onboarding_completed");
  localStorage.removeItem("onboarding_draft");
}

export async function loginWithToken(
  token: string,
  role: "student" | "parent"
): Promise<AuthResponse> {
  return api.post<AuthResponse>("/auth/token-login", {
    token,
    login_type: role,
  });
}

export async function loginAdmin(
  phone: string,
  password: string
): Promise<AuthResponse> {
  return api.post<AuthResponse>("/auth/admin-login", { phone, password });
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return api.get<AuthUser>("/auth/me");
}
```

---

## 9. API 客户端增强

修改 `src/lib/api.ts`，增加 401 自动跳转：

```typescript
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  // ... 现有逻辑

  if (!res.ok) {
    // 401 自动跳转
    if (res.status === 401) {
      clearAuth();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new ApiError({ code: "UNAUTHORIZED", message: "登录已过期", detail: {} });
    }

    const body = await res.json().catch(() => ({
      error: { code: "NETWORK_ERROR", message: "网络请求失败", detail: {} },
    }));
    throw new ApiError(body.error);
  }

  // ... 现有逻辑
}
```

新增分页请求方法：

```typescript
export const api = {
  get: <T>(path: string) => request<T>(path),
  getPaginated: <T>(path: string) =>
    request<{ items: T[]; page: number; page_size: number; total: number; total_pages: number }>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
```

---

## 10. 实施步骤（10 步）

| 步骤 | 内容 | 文件变更 | 验证方式 |
|------|------|----------|----------|
| **1** | 后端 CORS + 前端 API 增强 | `main.py`, `config.py`, `api.ts` | 前端 fetch 无 CORS 报错 |
| **2** | 认证模块 + 登录页 | `auth.ts`, `login/page.tsx` | 三种角色登录成功，token 正确存储 |
| **3** | 路由守卫 + 根页面 | `page.tsx` | 无 token → /login；有 token → 按角色跳转 |
| **4** | SWR hooks + 仪表板 | `hooks.ts`, `dashboard/page.tsx` | 仪表板展示真实数据（或空态） |
| **5** | 今日计划 + 入学问卷 | `plan/today/page.tsx`, `onboarding/page.tsx` | 任务状态更新持久化；问卷提交到后端 |
| **6** | 上传页 + OCR 轮询 | `upload/page.tsx` | 文件上传成功，OCR 状态实时更新 |
| **7** | 答疑页 SSE 集成 | `qa/page.tsx` | 流式回复逐字展示，知识点/策略标签正确 |
| **8** | 错题本 + 周报 + 分享 | `errors/page.tsx`, `report/weekly/page.tsx`, `share/[token]/page.tsx` | 分页筛选正确，分享链接可访问 |
| **9** | 家长端 + 管理端 | 4 个页面 | 家长看脱敏数据，管理员可切换模式 |
| **10** | AppHeader + mock 清理 | `app-header.tsx`, 删除 `mock-data.ts` | 模式切换持久化，无 mock 残留 |

---

## 11. 前后端 API 路径映射表

| 前端 Hook / 调用 | HTTP 方法 | 后端路径 | 备注 |
|------------------|-----------|----------|------|
| `loginWithToken()` | POST | `/auth/token-login` | 学生/家长 |
| `loginAdmin()` | POST | `/auth/admin-login` | 管理员 |
| `fetchCurrentUser()` | GET | `/auth/me` | 验证 token |
| `api.post("/auth/refresh")` | POST | `/auth/refresh` | token 刷新 |
| `api.post("/student/onboarding/submit")` | POST | `/student/onboarding/submit` | |
| `api.get("/student/onboarding/status")` | GET | `/student/onboarding/status` | |
| `useDailyPlan()` | GET | `/student/plan/today` | |
| `api.post("/student/plan/generate")` | POST | `/student/plan/generate` | |
| `api.patch("/student/plan/mode")` | PATCH | `/student/plan/mode` | |
| `api.patch("/student/plan/tasks/{id}")` | PATCH | `/student/plan/tasks/{id}` | |
| `useRecentUploads()` | GET | `/student/material/list` | 分页 |
| `api.post("/student/material/upload")` | POST | `/student/material/upload` | FormData |
| `useUploadOcrStatus()` | GET | `/student/material/{id}/ocr-status` | 轮询 |
| `api.post("/student/material/{id}/retry-ocr")` | POST | `/student/material/{id}/retry-ocr` | |
| `api.post("/student/qa/chat")` | POST | `/student/qa/chat` | 同步模式 |
| `streamRequest("/student/qa/chat/stream")` | POST | `/student/qa/chat/stream` | SSE |
| `useQAHistory()` | GET | `/student/qa/history` | 分页 |
| `useSessionDetail()` | GET | `/student/qa/sessions/{id}` | |
| `useErrorList()` | GET | `/student/errors` | 分页+筛选 |
| `useErrorSummary()` | GET | `/student/errors/summary` | |
| `api.post("/student/errors/{id}/recall")` | POST | `/student/errors/{id}/recall` | |
| `api.post("/student/errors/batch-recall")` | POST | `/student/errors/batch-recall` | |
| `useKnowledgeStatus()` | GET | `/student/knowledge/status` | |
| `useWeeklyReport()` | GET | `/student/report/weekly` | |
| `api.post("/student/report/share")` | POST | `/student/report/share` | |
| `useSWR("/share/{token}")` | GET | `/share/{token}` | 无认证 |
| `useParentWeeklyReport()` | GET | `/parent/report/weekly` | |
| `api.post("/parent/report/share")` | POST | `/parent/report/share` | |
| `useParentRisk()` | GET | `/parent/profile/risk` | |
| `useParentTrend()` | GET | `/parent/profile/trend` | |
| `api.post("/parent/profile/supplement")` | POST | `/parent/profile/supplement` | |
| `api.post("/parent/exam/record")` | POST | `/parent/exam/record` | |
| `useSystemMode()` | GET | `/admin/system/mode` | |
| `api.post("/admin/system/mode")` | POST | `/admin/system/mode` | |
| `usePendingCorrections()` | GET | `/admin/corrections/pending` | 分页 |
| `api.post("/admin/corrections/ocr")` | POST | `/admin/corrections/ocr` | |
| `api.post("/admin/corrections/knowledge")` | POST | `/admin/corrections/knowledge` | |
| `useAdminMetrics()` | GET | `/admin/metrics/today` | |
| `useAdminHealth()` | GET | `/admin/metrics/health` | |
| `useModelCalls()` | GET | `/admin/metrics/model-calls` | |

---

## 12. 类型对齐注意事项

前端 `types/api.ts` 与后端 `schemas/*.py` 大部分已对齐，以下需关注：

| 字段 | 前端类型 | 后端类型 | 处理方式 |
|------|----------|----------|----------|
| `StudyUpload.subject` | `Subject` (中文字符串) | `subject_id: int` | 前端用 `getSubject(id).name` 转换 |
| `QASession.subject` | `Subject` (中文字符串) | `subject_id: int` | 同上 |
| `QASession.title` | `string` | 后端无此字段，需从首条消息提取 | 前端取 `messages[0].content.slice(0, 20)` |
| `ErrorBookItem.knowledge_points` | `{id?, name}[]` | `knowledge_points: JSONB` | 直接使用，结构一致 |
| `CorrectionItem.type` | `string` | `target_type: string` | 字段名不同，需映射 |
| `CorrectionItem.student_name` | `string` | 后端需 join User 表 | 确认后端 response 包含此字段 |

前端需要一个 subject ID → 中文名映射（已有 `src/lib/subjects.ts`）。

---

## 13. 设计决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 数据获取库 | SWR | 已安装，轻量，支持自动重新验证和缓存 |
| 状态管理 | 无全局状态（SWR 缓存 + localStorage） | MVP 阶段够用，避免引入 Redux/Zustand 复杂度 |
| Token 存储 | localStorage | 简单可靠；httpOnly cookie 需要后端配合，MVP 不需要 |
| 401 处理 | api.ts 全局拦截 + 跳转 /login | 统一处理，避免每个页面重复判断 |
| OCR 轮询 | SWR refreshInterval | 利用 SWR 内置轮询，代码简洁 |
| SSE 实现 | fetch + ReadableStream（已有 stream.ts） | 支持 POST + Auth header，比 EventSource 更灵活 |
| mock-data.ts | 联调完成后删除 | 避免残留引用导致混淆 |
