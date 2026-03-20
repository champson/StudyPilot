# Phase 3 详细设计：LLM Agent 集成

> **状态**：已实现（2026-03-20 完成）。本文档为实现后的架构记录。

## 1. 概述

### 1.1 目标

将 Phase 2 中所有 stub 实现替换为真实的 LLM Agent 调用，实现：
- 基于学情的个性化计划生成（Planning Agent）
- 多轮引导式答疑 + 流式输出（Tutoring Agent）
- OCR 图文识别与题目结构化（Extraction Agent）
- 答疑后学情自动评估（Assessment Agent）
- 意图路由分类（Routing Agent）
- 双模式模型路由 + 自动降级 + 成本追踪

### 1.2 范围边界

**包含**：
- 5 个 Agent 的完整实现
- ModelRouter 双模式架构（normal/best）
- YAML 驱动的模型配置
- 成本追踪与调用日志
- 知识点状态自动更新（Assessment → KnowledgeStatus）
- 错题本自动入库（答疑中产生的错题）
- 周报自动生成（Celery Beat 定时任务）
- 入学问卷 → 初始状态映射

**不包含**：
- 阿里云 OSS 实际对接（本阶段继续使用本地文件存储）
- 考试冲刺模式（P1，后续阶段）
- 前端联调（Phase 4）

### 1.3 依赖文档

| 文档 | 关联章节 |
|------|---------|
| `prd.md` | §11.1 计划生成逻辑, §11.2 状态模型 |
| `architecture_design.md` | §3 模型路由, §4 Agent 编排 |
| `api-contract.md` | §4-9 全部接口契约 |
| `er-diagram.md` | 全部表结构 |

---

## 2. 新增文件清单

```
server/
├── config/
│   └── model_config.yaml              # Agent 模型映射配置
├── app/
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── model_router.py            # 模型路由器（双模式 + 降级 + 日志）
│   │   ├── cost_tracker.py            # 成本计算 + ModelCallLog 写入
│   │   ├── prompts/
│   │   │   ├── __init__.py
│   │   │   ├── routing.py             # Routing Agent system prompt
│   │   │   ├── planning.py            # Planning Agent system prompt
│   │   │   ├── tutoring.py            # Tutoring Agent system prompt
│   │   │   ├── assessment.py          # Assessment Agent system prompt
│   │   │   └── extraction.py          # Extraction Agent system prompt
│   │   └── agents/
│   │       ├── __init__.py
│   │       ├── routing.py             # 意图分类 Agent
│   │       ├── planning.py            # 计划生成 Agent
│   │       ├── tutoring.py            # 答疑 Agent（sync + stream）
│   │       ├── assessment.py          # 学情评估 Agent
│   │       └── extraction.py          # OCR / 图文识别 Agent
│   └── tasks/
│       └── weekly_report.py           # 周报生成定时任务
```

**修改的已有文件**：

| 文件 | 变更内容 |
|------|---------|
| `app/core/config.py` | 增加 LLM provider API keys、MODEL_CONFIG_PATH |
| `app/services/plan.py` | `generate_plan_stub()` → `generate_plan()`，调用 Planning Agent |
| `app/services/qa.py` | `chat_sync()` / `chat_stream_stub()` 调用 Tutoring Agent |
| `app/services/knowledge.py` | 增加 `update_mastery_state()` 和 `batch_init_from_onboarding()` |
| `app/services/student_profile.py` | `submit_onboarding()` 增加初始状态映射调用 |
| `app/tasks/ocr.py` | 调用 Extraction Agent 替换 sleep stub |
| `app/tasks/celery_app.py` | 增加 Beat schedule（周报生成） |
| `requirements.txt` | 增加 openai, anthropic, pyyaml, httpx（LLM 调用） |

---

## 3. 模型路由架构

### 3.1 YAML 配置（`config/model_config.yaml`）

```yaml
current_mode: normal  # 初始默认值；运行时由 Redis 控制

agents:
  routing:
    normal:
      provider: dashscope
      model: qwen-turbo
      timeout: 10
      max_retries: 1
      temperature: 0.0
    best:
      provider: dashscope
      model: qwen-turbo
      timeout: 10
      max_retries: 1
      temperature: 0.0

  extraction:
    normal:
      provider: dashscope
      model: qwen-vl-max
      timeout: 30
      max_retries: 2
      temperature: 0.1
    best:
      provider: openai
      model: gpt-4o
      timeout: 45
      max_retries: 2
      temperature: 0.1

  planning:
    normal:
      provider: dashscope
      model: qwen-max
      timeout: 30
      max_retries: 2
      temperature: 0.3
    best:
      provider: deepseek
      model: deepseek-chat
      timeout: 30
      max_retries: 2
      temperature: 0.3

  tutoring:
    normal:
      provider: deepseek
      model: deepseek-chat
      timeout: 60
      max_retries: 2
      temperature: 0.7
      stream: true
    best:
      provider: anthropic
      model: claude-sonnet-4-20250514
      timeout: 60
      max_retries: 2
      temperature: 0.7
      stream: true

  assessment:
    normal:
      provider: dashscope
      model: qwen-turbo
      timeout: 15
      max_retries: 2
      temperature: 0.1
    best:
      provider: deepseek
      model: deepseek-chat
      timeout: 30
      max_retries: 2
      temperature: 0.1

providers:
  dashscope:
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: DASHSCOPE_API_KEY
  deepseek:
    base_url: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
  anthropic:
    base_url: https://api.anthropic.com/v1  # 仅作配置记录，实际使用原生 SDK
    api_key_env: ANTHROPIC_API_KEY
  openai:
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
```

### 3.2 ModelRouter 核心逻辑

**职责**：
1. 从 Redis 读取当前运行模式（normal/best），YAML 文件提供默认值
2. 根据 agent_name + mode 查找 YAML 配置
3. 构造对应的 SDK client 调用 LLM（OpenAI-compatible 或 Anthropic 原生）
4. 调用失败时自动降级到另一模式
5. 通过 `_record_call()` 写入 ModelCallLog（含成本估算）

**关键方法**：
- `async def current_mode() -> str` — 从 Redis 读取，降级到 YAML 默认值
- `_get_client(provider)` — 根据 provider 类型返回 `AsyncOpenAI` 或 `AsyncAnthropic`
- `_call_with_config()` / `_call_anthropic()` — 同步调用，自动区分 API 格式
- `_stream_with_config()` / `_stream_anthropic()` — 流式调用
- `invoke()` — 同步调用 + 双模式降级 + 成本记录
- `invoke_stream()` — 流式调用 + 双模式降级（已 yield chunk 后不再降级）

**Anthropic 适配**：Anthropic 不提供 OpenAI-compatible 端点，使用原生 `anthropic` SDK。
`_extract_system_message()` 将 OpenAI 格式的 system message 分离为 Anthropic 的 `system` 参数。

**关键设计决策**：

- 通义千问、DeepSeek、OpenAI 使用 `openai` SDK 的 `base_url` 适配；Anthropic 使用原生 `anthropic` SDK
- 运行模式存 Redis（`system:run_mode`），所有进程即时感知，无需重启
- YAML 文件仅作初始默认值和持久化备份
- 单例模式 `get_model_router()` / `reset_model_router()` 管理全局实例

### 3.3 成本追踪

```python
# app/llm/cost_tracker.py

MODEL_PRICING = {  # 元/1K tokens
    "qwen-vl-max":    {"input": 0.020, "output": 0.020},
    "qwen-max":       {"input": 0.020, "output": 0.060},
    "qwen-turbo":     {"input": 0.002, "output": 0.006},
    "deepseek-chat":  {"input": 0.001, "output": 0.002},
    "claude-sonnet-4-20250514": {"input": 0.021, "output": 0.105},
    "gpt-4o":         {"input": 0.035, "output": 0.105},
}

async def log_model_call(
    db: AsyncSession,
    *,
    request_id: UUID,
    student_id: int | None,
    agent_name: str,
    mode: str,
    provider: str,
    model: str,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    is_fallback: bool,
    success: bool,
    error_message: str | None = None,
) -> None:
    pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000

    log = ModelCallLog(
        request_id=request_id,
        student_id=student_id,
        agent_name=agent_name,
        mode=mode,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        is_fallback=is_fallback,
        success=success,
        error_message=error_message,
        estimated_cost=cost,
    )
    db.add(log)
    await db.flush()
```

---

## 4. Agent 详细设计

### 4.1 Routing Agent（意图分类）

**触发场景**：QA chat 接口收到用户消息时。

**输入**：
```json
{
  "message": "导数怎么求?",
  "has_attachments": false,
  "session_context": "新会话" | "已有会话追问"
}
```

**输出**（JSON，structured output）：
```json
{
  "intent": "ask_question",  // ask_question | follow_up | upload_question | chat | operate
  "confidence": 0.95,
  "route_to": "tutoring"     // tutoring | extraction | none
}
```

**System Prompt 核心要求**：
- 仅做意图分类，不生成回答
- 有附件（图片）→ 倾向 `upload_question`
- 已有会话上下文 + 问题追问 → `follow_up`
- 与学习无关的闲聊 → `chat`（不路由到 tutoring）
- 指令类操作（"切换模式""标记完成"）→ `operate`

**实现要点**：
- 使用 `qwen-turbo`（最快最便宜），两种模式配置相同
- Timeout 10s，失败不降级，直接默认路由到 `tutoring`
- 不需要 LangGraph，单次 LLM 调用 + JSON parse

### 4.2 Planning Agent（计划生成）

**触发场景**：`POST /student/plan/generate`

**数据收集（调用前）**：

```python
async def collect_planning_context(db, student_id: int) -> dict:
    """从 DB 收集 Planning Agent 所需的全部上下文"""
    return {
        "profile": {  # student_profiles
            "grade": "高二",
            "subject_combination": ["语文","数学","英语","物理","化学","地理"],
            "textbook_version": "沪教版",
        },
        "knowledge_mastery": [  # student_knowledge_status (聚合)
            {"subject_id": 1, "subject_name": "数学",
             "mastered": 12, "needs_consolidation": 8, "repeated_mistakes": 3},
        ],
        "subject_risks": [  # subject_risk_states (最新一周)
            {"subject_id": 1, "subject_name": "数学", "risk_level": "轻度风险"},
        ],
        "recent_errors": [  # error_book (近 7 天)
            {"subject_id": 1, "knowledge_point": "导数定义", "error_count": 3},
        ],
        "recent_uploads": [  # study_uploads (今日, ocr_status=completed)
            {"subject_id": 1, "upload_type": "homework", "extracted_topics": ["导数"]},
        ],
        "upcoming_exams": [  # exam_records (未来 14 天)
            {"subject_id": 1, "exam_type": "月考", "exam_date": "2026-03-28"},
        ],
        "available_minutes": 120,
        "learning_mode": "workday_follow",
        "today_weekday": 3,  # 周三
    }
```

**System Prompt 核心规则（源自 PRD §11.1）**：

```
你是一个学习计划生成器。根据学生的学情数据，生成今日学习计划。

## 模式优先规则

### 工作日跟学模式 (workday_follow)
优先级排序：
1. 今日校内同步（有今日上传内容的学科优先）
2. 今日错误较多（今日答疑/做题中错误多的学科）
3. 明日任务/测验（有近期考试的学科）
4. 近期反复错误（error_book 中 recall_fail 多的知识点所属学科）
5. 本周覆盖不足（本周尚未安排的学科补充）

### 周末复习模式 (weekend_review)
优先级排序：
1. 本周错题修复（本周错题最多的学科）
2. 薄弱知识点待修复（knowledge_status = "需要巩固" 或 "反复失误"）
3. 考试临近（14 天内有考试的学科）
4. 本周覆盖不足

## 学科数量规则
- 可用时间 < 30 分钟 或 任务强度 = high → 1 门
- 可用时间 30-60 分钟 → 2 门
- 可用时间 > 60 分钟 且 任务强度 ≤ medium → 3 门
- 绝不平均分配所有学科

## 输出格式（严格 JSON）
```

**输出格式**：
```json
{
  "recommended_subjects": [
    {
      "subject_id": 1,
      "reasons": ["今日校内同步", "今日错误较多"]
    },
    {
      "subject_id": 3,
      "reasons": ["本周覆盖不足"]
    }
  ],
  "tasks": [
    {
      "subject_id": 1,
      "task_type": "error_review",
      "title": "数学导数错题回顾",
      "description": "复习今日导数相关的 3 道错题，重点理解导数定义和求导法则",
      "knowledge_points": [42, 45],
      "sequence": 1,
      "estimated_minutes": 30,
      "difficulty": "medium"
    },
    {
      "subject_id": 1,
      "task_type": "exercise",
      "title": "数学导数练习",
      "description": "完成 5 道导数基础练习题",
      "knowledge_points": [42],
      "sequence": 2,
      "estimated_minutes": 25,
      "difficulty": "medium"
    },
    {
      "subject_id": 3,
      "task_type": "review",
      "title": "英语词汇复习",
      "description": "复习本周新学的 Unit 5 词汇",
      "knowledge_points": [],
      "sequence": 3,
      "estimated_minutes": 20,
      "difficulty": "low"
    }
  ],
  "reasoning": "工作日跟学模式。数学今日有上传作业且导数错题较多，优先安排错题回顾和练习。英语本周尚未覆盖，补充词汇复习。"
}
```

**实现要点**：
- LLM 调用前先做规则引擎粗排（`_rule_based_ranking()`），结果作为 prompt context
- 要求 LLM 输出严格 JSON（`response_format: {"type": "json_object"}`）
- JSON parse 失败时重试 1 次，仍失败则降级为 `generic_fallback`（Phase 2 的 stub 逻辑）
- `plan_content` JSONB 存储 LLM 原始输出（含 reasoning），API 不暴露
- `source` 字段标记：有今日上传 → `upload_corrected`；无上传但有历史 → `history_inferred`；LLM 失败 → `generic_fallback`

**降级路径**：
```
Planning Agent 调用
    ├─ 成功 → 解析 JSON → 创建 DailyPlan + PlanTask
    ├─ JSON 解析失败 → 重试 1 次
    │   ├─ 重试成功 → 同上
    │   └─ 重试失败 → 自动降级到 fallback model
    │       ├─ fallback 成功 → 同上
    │       └─ fallback 失败 → generic_fallback（硬编码 stub）
    └─ 超时/网络错误 → 自动降级到 fallback model（同上）
```

### 4.3 Tutoring Agent（答疑）

**触发场景**：
- `POST /student/qa/chat`（同步）
- `POST /student/qa/chat/stream`（流式 SSE）

**System Prompt 核心规则**：

```
你是一个高中学科辅导老师。遵循以下原则：

1. 引导式教学：不直接给答案，通过提问引导学生思考
2. 分步讲解：复杂问题分步骤解答，每步确认学生理解
3. 知识点关联：回答中明确标注涉及的知识点
4. 追问设计：每次回答后给出 1-2 个追问，检验理解
5. 错误诊断：如果学生答错，分析错因（计算/概念/粗心）
6. LaTeX 格式：数学公式使用 LaTeX 格式
```

**同步调用流程**：
```
用户消息 → Routing Agent (意图) → Tutoring Agent (回答) → 解析输出
    ↓                                                       ↓
save user_msg                                    save assistant_msg
                                                        ↓
                                              Assessment Agent (异步)
                                                        ↓
                                              更新 knowledge_status
                                              (可能) 写入 error_book
```

**流式调用流程**：
```
用户消息 → save user_msg → Routing Agent (快速意图)
    ↓
Tutoring Agent (stream)
    ↓ yield chunks
SSE: {"type":"chunk","content":"..."} × N
SSE: {"type":"knowledge_points","data":[...]}
SSE: {"type":"strategy","data":"hint"}
SSE: [DONE]
    ↓
save assistant_msg (拼接 chunks)
    ↓ (异步，不阻塞 SSE 响应)
Assessment Agent → update knowledge_status
```

**Tutoring Agent 输出结构（LLM 指令要求）**：

```
在回答的最后，请用以下格式输出元数据（用 --- 分隔）：

---METADATA---
knowledge_points: [{"id": 42, "name": "导数定义"}, {"id": 45, "name": "求导法则"}]
strategy: hint
follow_up_questions: ["你能举一个导数的实际应用例子吗？", "如何判断函数在某点是否可导？"]
error_diagnosis: null | {"type": "概念不清", "detail": "混淆了导数和微分的概念"}
---END---
```

**实现要点**：
- 流式时，`---METADATA---` 之前的内容逐 chunk 推送给前端
- 元数据部分在流结束后解析，不推送给前端
- 知识点 ID 匹配：LLM 输出的 name → 查 `knowledge_tree` 表反查 ID
- 如果 LLM 没有输出元数据分隔符，使用默认值（strategy=hint, knowledge_points=[]）

### 4.4 Assessment Agent（学情评估）

**触发场景**：每次 Tutoring Agent 回答完成后（异步触发，不阻塞用户）。

**触发方式**：
- 同步 chat：在 `chat_sync()` 尾部直接 await
- 流式 chat：在 `save_stream_assistant_message()` 之后，通过 Celery task 异步执行

**输入**：
```json
{
  "session_id": 123,
  "messages": [
    {"role": "user", "content": "导数怎么求?"},
    {"role": "assistant", "content": "...分步讲解..."},
    {"role": "user", "content": "哦我明白了，是用极限定义对吧"},
    {"role": "assistant", "content": "...确认并追问..."}
  ],
  "knowledge_points_involved": [
    {"id": 42, "name": "导数定义", "current_status": "初步接触"}
  ]
}
```

**输出（structured JSON）**：
```json
{
  "knowledge_point_updates": [
    {
      "knowledge_point_id": 42,
      "knowledge_point_name": "导数定义",
      "previous_status": "初步接触",
      "new_status": "需要巩固",
      "reason": "经提示后答对",
      "confidence": 0.85
    }
  ],
  "session_summary": {
    "total_questions": 2,
    "correct_first_try": 0,
    "correct_with_hint": 1,
    "incorrect": 1,
    "dominant_error_type": "概念不清"
  },
  "error_book_entries": [
    {
      "subject_id": 1,
      "question_summary": "导数定义的理解",
      "knowledge_point_ids": [42],
      "error_type": "概念不清",
      "entry_reason": "wrong"
    }
  ],
  "suggested_followup": "建议明日复习导数定义和求导法则"
}
```

**状态迁移规则（硬编码，LLM 仅建议）**：

| 触发 | 当前状态 | 新状态 |
|------|---------|-------|
| 一次答对（无提示） | 未观察/初步接触 | 需要巩固 (*)  |
| 经提示后答对 | 未观察/初步接触 | 需要巩固 |
| 答错/放弃 | 任意 | 初步接触（首次）/ 需要巩固（已接触）|
| 错题召回答对 | 需要巩固 | 基本掌握 |
| 错题召回答错（累计≥2） | 任意 | 反复失误 |
| 人工纠偏 | 任意 | 管理员指定 |

(*) 升至"基本掌握"需同一知识点在**不同会话**中答对 ≥ 2 次。

**实现要点**：
- Assessment Agent 的 LLM 输出仅作为**建议**
- 实际状态迁移由 `services/knowledge.py` 中的规则函数硬编码执行
- LLM 输出的 `knowledge_point_updates` 经过规则验证后才写入 DB
- `error_book_entries` 自动创建 ErrorBook 记录（检查 content_hash 去重）
- `structured_summary` 写入 `qa_sessions.structured_summary`

### 4.5 Extraction Agent（OCR / 图文识别）

**触发场景**：Celery task `process_ocr(upload_id)` 执行时。

**输入**：上传图片的 base64 或 URL。

**输出**：
```json
{
  "detected_subject": "数学",
  "detected_subject_id": 1,
  "questions": [
    {
      "index": 1,
      "type": "fill_in_blank",
      "content_text": "求函数 f(x) = x² + 3x 在 x = 2 处的导数",
      "content_latex": "求函数 $f(x) = x^2 + 3x$ 在 $x = 2$ 处的导数",
      "options": null,
      "answer": null,
      "knowledge_points": ["导数定义", "求导法则"]
    }
  ],
  "raw_text": "... OCR 全文 ..."
}
```

**实现要点**：
- 使用 VL（Vision-Language）模型，图片直接作为 multimodal 输入
- Qwen-VL-Max 通过 DashScope API，GPT-4o 通过 OpenAI API
- 输出严格 JSON，parse 失败重试 1 次
- 失败 → 创建 `manual_corrections` 记录（target_type="ocr"）
- 知识点 name → ID 映射通过查 `knowledge_tree` 表
- 结果存入 `study_uploads.ocr_result` + `study_uploads.extracted_questions`

---

## 5. 核心数据流

### 5.1 计划生成完整流程

```
POST /student/plan/generate
    │ {available_minutes: 120, learning_mode: null}
    ▼
┌───────────────────────────────┐
│ 1. 检查 onboarding_completed │
│ 2. 检查今日是否已有计划       │
│ 3. 确定 learning_mode         │
│    (传入值 > 用户默认 > 自动)  │
└───────────┬───────────────────┘
            ▼
┌───────────────────────────────┐
│ collect_planning_context()    │
│ - profile, knowledge_mastery  │
│ - subject_risks, recent_errors│
│ - recent_uploads, exams       │
└───────────┬───────────────────┘
            ▼
┌───────────────────────────────┐
│ rule_based_ranking()          │
│ - 按模式内优先级粗排学科      │
│ - 输出候选学科 + 原因标签     │
└───────────┬───────────────────┘
            ▼
┌───────────────────────────────┐
│ Planning Agent (LLM)          │
│ - 输入: context + 粗排结果    │
│ - 输出: tasks[], reasons[]    │
│ - 降级: generic_fallback      │
└───────────┬───────────────────┘
            ▼
┌───────────────────────────────┐
│ 持久化                         │
│ - DailyPlan (plan_content=LLM │
│   原始输出, source, mode)      │
│ - PlanTask × N (从 LLM 输出)  │
│ - ModelCallLog                │
└───────────┬───────────────────┘
            ▼
  返回 DailyPlanOut (含 tasks[])
```

### 5.2 答疑流式完整流程

```
POST /student/qa/chat/stream
    │ {session_id, message, subject_id, task_id}
    ▼
┌──────────────────────────────┐
│ save_user_message()          │
│ → QaSession + QaMessage(user)│
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ Routing Agent (可选，快速)    │
│ → intent classification      │
│ → 如果 intent=chat, 直接返回  │
│   "请聚焦学习问题" 的拒绝回复  │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ Tutoring Agent (stream)      │
│ → yield SSE chunks           │
│ → 累积 full_content          │
│ → 解析 ---METADATA--- 部分   │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ save_assistant_message()     │
│ → QaMessage(assistant) +     │
│   intent, knowledge_points,  │
│   tutoring_strategy          │
└──────────┬───────────────────┘
           ▼ (异步，Celery task)
┌──────────────────────────────┐
│ Assessment Agent             │
│ → 评估本轮对话               │
│ → 输出 knowledge_updates[]   │
│ → 输出 error_book_entries[]  │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ apply_assessment_results()   │
│ → update student_knowledge   │
│   _status (规则验证后)        │
│ → create error_book entries  │
│ → write knowledge_update_logs│
│ → update qa_sessions         │
│   .structured_summary        │
└──────────────────────────────┘
```

### 5.3 OCR 异步处理流程

```
POST /student/material/upload
    │ multipart: file + upload_type + subject_id
    ▼
┌───────────────────────────────┐
│ 1. 保存文件到本地磁盘         │
│ 2. 计算 SHA256 → file_hash    │
│ 3. 创建 StudyUpload 记录      │
│    (ocr_status="pending")     │
│ 4. process_ocr.delay(id)      │
└───────────┬───────────────────┘
            ▼ (Celery Worker)
┌───────────────────────────────┐
│ process_ocr(upload_id)        │
│ 1. 读取文件                   │
│ 2. Extraction Agent (VL LLM)  │
│ 3. 解析输出 JSON              │
│    - detected_subject_id      │
│    - questions[]               │
│    - knowledge_points[]       │
│ 4. 更新 study_uploads:        │
│    ocr_status="completed"     │
│    ocr_result=结构化JSON       │
│    subject_id=detected        │
│    knowledge_points=matched   │
│ 5. ModelCallLog               │
└───────────┬───────────────────┘
            │
            ├─ 成功 → ocr_status="completed"
            │
            ├─ 失败（重试 ≤ 2 次）
            │   └─ Celery autoretry(countdown=30)
            │
            └─ 超过重试 → ocr_status="failed"
                └─ 创建 ManualCorrection(target_type="ocr")
```

### 5.4 入学问卷 → 初始状态映射

```
POST /student/onboarding/submit
    │ {grade, subject_combination, weak_subjects,
    │  recent_exam_scores, daily_study_minutes, ...}
    ▼
┌───────────────────────────────┐
│ 1. 验证 onboarding_completed  │
│    == False，否则 409          │
│ 2. 存储 onboarding_data JSONB │
└───────────┬───────────────────┘
            ▼
┌───────────────────────────────┐
│ batch_init_from_onboarding()  │
│                               │
│ Rule 1: weak_subjects →       │
│   章级知识点 → "初步接触"      │
│                               │
│ Rule 2: exam_score < 60% →    │
│   学科风险 → "中度风险"        │
│                               │
│ Rule 3: exam_score < 75% →    │
│   学科风险 → "轻度风险"        │
│                               │
│ Rule 4: weak + 无成绩 →       │
│   学科风险 → "轻度风险"(兜底)  │
└───────────┬───────────────────┘
            ▼
┌───────────────────────────────┐
│ 批量写入:                      │
│ - student_knowledge_status    │
│ - subject_risk_states         │
│ - knowledge_update_logs       │
│ 设置 onboarding_completed=True│
└───────────────────────────────┘
```

### 5.5 周报自动生成（Celery Beat）

```
每周日 23:30 (Asia/Shanghai)
    ▼
┌───────────────────────────────┐
│ generate_weekly_reports()     │
│                               │
│ for each active student:      │
│ 1. 汇总本周数据:              │
│    - 使用天数                  │
│    - 总学习时长                │
│    - 完成任务数/总任务数       │
│    - 各科错题统计              │
│    - 各科知识点状态汇总        │
│ 2. 计算学科风险状态变更        │
│ 3. 调用 LLM (Assessment)     │
│    生成文字总结和建议           │
│ 4. 写入 weekly_reports:       │
│    - student_view_content     │
│    - parent_view_content      │
│    - share_summary            │
└───────────────────────────────┘
```

---

## 6. 新增依赖

```
# requirements.txt 新增
openai>=1.0.0           # LLM 调用 SDK（OpenAI-compatible providers: DashScope, DeepSeek, OpenAI）
anthropic>=0.40.0       # Anthropic 原生 SDK（Claude 不支持 OpenAI-compatible 接口）
pyyaml>=6.0             # 模型配置文件解析
```

**不需要**的依赖（简化决策）：
- ~~langchain / langgraph~~：5 个 Agent 均为单次 LLM 调用 + 规则引擎组合，不需要 LangGraph 的状态机编排
- ~~dashscope SDK~~：通义千问通过 OpenAI-compatible endpoint 接入

**理由**：
- 通义千问、DeepSeek、OpenAI 通过 `openai` SDK 的 `AsyncOpenAI(base_url=...)` 适配
- Anthropic 使用原生 `anthropic` SDK（`AsyncAnthropic`），因其不提供 OpenAI-compatible 端点
- LangGraph 在当前 MVP 规模（5 学生）下没有必要。Agent 之间的编排通过 Python 函数调用 + Celery 异步任务即可实现

---

## 7. Config 变更

```python
# app/core/config.py 新增字段

class Settings(BaseSettings):
    # ... 已有字段 ...

    # LLM Provider API Keys
    DASHSCOPE_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Model config
    MODEL_CONFIG_PATH: str = "config/model_config.yaml"
```

---

## 8. 数据库变更

### 8.1 新增表：subject_risk_states

Phase 2 的 ORM 模型中尚未包含 `subject_risk_states` 表。需要新增：

```python
# app/models/knowledge.py 新增

class SubjectRiskState(Base):
    __tablename__ = "subject_risk_states"
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "effective_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_profiles.id"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subjects.id"), nullable=False
    )
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="稳定")
    effective_week: Mapped[str] = mapped_column(String(10), nullable=False)
    calculation_detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

**Alembic 迁移**：创建 `alembic/versions/xxx_add_subject_risk_states.py`

### 8.2 已有表无需变更

Phase 2 已定义的所有表结构满足 Phase 3 需求：
- `model_call_logs` ✅ 已有
- `manual_corrections` ✅ 已有
- `student_knowledge_status` ✅ 已有
- `knowledge_update_logs` ✅ 已有
- `qa_sessions.structured_summary` ✅ 已有 JSONB 字段
- `qa_messages.intent/knowledge_points/tutoring_strategy` ✅ 已有
- `study_uploads.ocr_result/extracted_questions/knowledge_points` ✅ 已有

---

## 9. 实施顺序（12 步）

| 步骤 | 内容 | 新增/修改文件 | 依赖 |
|------|------|-------------|------|
| **1** | 基础设施：config 扩展 + requirements + model_config.yaml | 3 | 无 |
| **2** | ModelRouter + CostTracker | 2 新增 | 步骤 1 |
| **3** | Alembic 迁移：subject_risk_states 表 | 1 迁移 + 1 model | 步骤 1 |
| **4** | Routing Agent（prompt + agent） | 2 新增 | 步骤 2 |
| **5** | Planning Agent（prompt + agent + service 改造） | 3 新增 + 1 修改 | 步骤 2, 4 |
| **6** | Tutoring Agent（prompt + agent + service 改造） | 3 新增 + 1 修改 | 步骤 2, 4 |
| **7** | Assessment Agent（prompt + agent + knowledge service 增强） | 3 新增 + 1 修改 | 步骤 6 |
| **8** | Extraction Agent（prompt + agent + OCR task 改造） | 3 新增 + 1 修改 | 步骤 2 |
| **9** | 入学问卷状态初始化（knowledge service + profile service 增强） | 2 修改 | 步骤 3, 7 |
| **10** | 周报自动生成（Celery Beat task） | 1 新增 + 1 修改 | 步骤 7 |
| **11** | Admin 模式切换增强（与 ModelRouter 联动） | 1 修改 | 步骤 2 |
| **12** | 测试：每模块 1 个测试文件，mock LLM 响应 | ~8 测试文件 | 全部 |

---

## 10. 测试计划

### 10.1 单元测试（mock LLM）

所有 Agent 测试通过 mock `ModelRouter.invoke()` / `invoke_stream()` 返回预设 JSON：

| 测试文件 | 覆盖内容 |
|---------|---------|
| `tests/test_model_router.py` | 模式读取、配置加载、降级逻辑、client 构造 |
| `tests/test_routing_agent.py` | 意图分类各场景、默认路由 |
| `tests/test_planning_agent.py` | 上下文收集、规则引擎粗排、LLM 输出解析、降级到 fallback |
| `tests/test_tutoring_agent.py` | 同步回答、流式 chunk、元数据解析、知识点匹配 |
| `tests/test_assessment_agent.py` | 状态迁移规则、错题自动入库、structured_summary |
| `tests/test_extraction_agent.py` | OCR 输出解析、知识点匹配、失败创建纠偏 |
| `tests/test_cost_tracker.py` | 成本计算、ModelCallLog 写入 |
| `tests/test_weekly_report.py` | 周数据汇总、周报生成 |

### 10.2 集成测试

端到端流程验证（使用 mock LLM）：
1. token-login → submit onboarding → 验证初始知识点状态已写入
2. generate plan → 验证 DailyPlan + PlanTask 已创建，source 正确
3. chat (sync) → 验证 QaMessage 含 intent/knowledge_points
4. chat (stream) → 验证 SSE chunk 格式 + assistant_msg 已持久化
5. 验证 Assessment 后 student_knowledge_status 已更新
6. upload → process_ocr → 验证 ocr_result + extracted_questions
7. 模式切换 → 验证 Redis 写入 + 后续 plan 使用新模式

### 10.3 通过标准

| 指标 | 标准 |
|------|------|
| 计划生成 | 给定固定学情，输出 1-3 科目，source 标记正确 |
| 答疑 | 回答含 knowledge_points，流式 chunk 格式正确 |
| 状态迁移 | 20 个 mock 场景，规则判断 100% 正确 |
| OCR | mock 输出 parse 成功率 100%；失败时创建纠偏 |
| 模型路由 | 正常模式→国产 LLM；最优模式→GPT-4o/Claude；失败降级 |
| 成本追踪 | 每次调用 ModelCallLog 正确写入 |
| Agent 超时 | 30s 超时后返回友好错误或降级 |

---

## 11. 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 放弃 LangGraph | 纯 Python 函数 + Celery | MVP 5 学生，Agent 间无复杂状态机，不需要 Graph 编排的开销 |
| OpenAI SDK + Anthropic SDK | `openai` 适配大部分 provider，`anthropic` 适配 Claude | Anthropic 不提供 OpenAI-compatible 端点，需原生 SDK；其余 provider 统一 OpenAI-compatible |
| Assessment 结果用规则验证 | LLM 建议 + 硬编码规则 | 状态迁移规则是确定性的，不能完全依赖 LLM 的不确定输出 |
| 流式元数据分隔符 | `---METADATA---` 约定 | 避免复杂的结构化输出解析，在流式场景下简单可靠 |
| 规则引擎粗排 + LLM 精排 | 混合方案 | 规则引擎保证底线合理性，LLM 提供个性化和创造性 |
| 周报 LLM 生成 | Assessment Agent 复用 | 周报的文字总结需要 LLM 能力，但评估逻辑与 Assessment 一致 |
| 不引入 OSS | 本地磁盘 | MVP 阶段 5 个学生，本地存储足够，后续再迁移 |
