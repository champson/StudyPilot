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

#### 4.1.1 职责定义

根据用户输入判断意图，路由到对应 Agent。

#### 4.1.2 触发场景

QA chat 接口收到用户消息时。

#### 4.1.3 输入/输出规范

**输入**：
```json
{
  "message": "导数怎么求?",
  "has_attachments": false,
  "session_context": "new_session" | "existing_session"
}
```

**输出**（JSON，structured output）：
```json
{
  "intent": "ask",  // ask | follow_up | upload_question | chat | operate(*)
  "confidence": 0.95,
  "route_to": "tutoring"     // tutoring | extraction | none
}
```

> (*) `operate` 为 Routing Agent 内部使用的意图，用于指令类操作（如"切换模式"、"标记完成"），不会写入 `qa_messages.intent`。写入数据库的意图值与 API 契约 `MessageIntent` 类型一致：`ask | follow_up | upload_question | chat`。
```

#### 4.1.4 System Prompt 模板

```
你是一个意图分类器。分析用户消息，判断其意图类别。

## 输入
- message: 用户消息文本
- has_attachments: 是否有附件（图片）
- session_context: "new_session"（新会话）或 "existing_session"（已有会话）

## 意图类别定义
1. **upload_question**: 用户上传图片询问题目（has_attachments=true 且问题相关）
2. **ask**: 首次提出学习相关问题（新会话或首个学科问题）
3. **follow_up**: 追问、补充说明、请求进一步解释（已有会话上下文）
4. **chat**: 与学习无关的闲聊、问候、感谢
5. **operate**: 指令类操作（"切换模式"、"标记完成"、"看下一题"）— *内部路由用，不写入数据库*

## 路由规则
- upload_question → extraction
- ask, follow_up → tutoring
- chat, operate → none

## 输出格式
严格输出 JSON，不要包含任何其他文本：
{"intent": "<类别>", "confidence": <0.0-1.0>, "route_to": "<目标>"}

## 示例
输入: {"message": "导数怎么求?", "has_attachments": false, "session_context": "new_session"}
输出: {"intent": "ask", "confidence": 0.95, "route_to": "tutoring"}

输入: {"message": "明白了，谢谢", "has_attachments": false, "session_context": "existing_session"}
输出: {"intent": "chat", "confidence": 0.88, "route_to": "none"}
```

#### 4.1.5 约束条件

| 约束项 | 规则 |
|--------|------|
| 输出格式 | 必须为严格 JSON，不含多余文本 |
| 响应延迟 | <500ms（轻量级任务）|
| confidence 阈值 | <0.6 时标记为 `uncertain`，默认路由到 tutoring |
| 附件处理 | has_attachments=true 时优先考虑 upload_question |

#### 4.1.6 工具集

无（纯推理 Agent，不调用外部工具）。

#### 4.1.7 失败策略

| 失败场景 | 处理策略 |
|---------|----------|
| JSON 解析失败 | 默认路由到 `tutoring`（intent=ask）|
| LLM 超时（3s）| 降级为基于关键词的规则匹配 |
| API 异常 | 使用 fallback 规则引擎（关键词匹配） |

**降级规则引擎伪代码**：
```python
def fallback_intent_classify(message: str, has_attachments: bool) -> dict:
    if has_attachments:
        return {"intent": "upload_question", "confidence": 0.7, "route_to": "extraction"}
    
    keywords_operate = ["切换", "标记", "下一题", "完成", "跳过"]
    keywords_chat = ["谢谢", "好的", "明白", "你好", "再见"]
    
    if any(kw in message for kw in keywords_operate):
        return {"intent": "operate", "confidence": 0.6, "route_to": "none"}
    if any(kw in message for kw in keywords_chat):
        return {"intent": "chat", "confidence": 0.6, "route_to": "none"}
    
    return {"intent": "ask", "confidence": 0.5, "route_to": "tutoring"}
```

#### 4.1.8 模型配置

| 模式 | Provider | Model | 说明 |
|------|----------|-------|------|
| normal | dashscope | qwen-turbo | 轻量级任务，最快最便宜 |
| best | dashscope | qwen-turbo | 路由无需高级模型，两种模式相同 |

**实现要点**：
- 使用 `qwen-turbo`，两种模式配置相同
- Timeout 10s，失败不降级到 best 模式，直接使用 fallback 规则
- 不需要 LangGraph，单次 LLM 调用 + JSON parse

### 4.2 Planning Agent（计划生成）

#### 4.2.1 职责定义

根据学情快照生成个性化学习计划。

#### 4.2.2 触发场景

`POST /student/plan/generate`

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

#### 4.2.3 System Prompt 模板

```
你是一个学习计划生成器。根据学生的学情数据，生成今日学习计划。

## 输入数据
- student_profile: 学生档案（年级、选科、教材版本）
- knowledge_status_snapshot: 各学科知识点掌握情况
- recent_errors: 近 7 天错题统计
- upcoming_exams: 近期考试安排
- learning_mode: "workday_follow" | "weekend_review"
- available_minutes: 可用学习时间（分钟）

## 学科推荐规则

### 工作日跟学模式 (workday_follow)
评分因子及权重：
1. 今日校内同步（有当日上传）：+40
2. 今日错误较多（当日错题 ≥3）：+30
3. 明日任务/测验（upcoming_exams 在 1 天内）：+25
4. 近期反复错误（反复失误知识点 ≥2）：+20
5. 本周覆盖不足（本周该科任务 <2）：+15

### 周末复习模式 (weekend_review)
评分因子及权重：
1. 本周错题修复（本周新增错题数）：+35
2. 薄弱知识点待修复（反复失误数）：+30
3. 考试临近（upcoming_exams 在 7 天内）：+25
4. 最近成绩下滑（近 2 次成绩环比下降 ≥5%）：+20
5. 本周覆盖不足（本周该科任务 <2）：+15

## 学科数量规则
- 可用时间 ≤ 60 分钟 → 推荐 1 门
- 可用时间 60-120 分钟 → 推荐 2 门
- 可用时间 > 120 分钟 → 推荐 3 门
- 单科任务时间 ≥ 15 分钟
- 总时间不超过 available_minutes 的 110%

## 任务类型分配
- error_review: 有未召回错题时优先安排（占比 30-50%）
- practice: 有新上传内容时安排（占比 20-40%）
- consolidation: 需要巩固的知识点（占比 20-30%）
- lecture: 首次接触的知识点（占比 10-20%）

## 输出格式（严格 JSON）
{
  "recommended_subjects": [
    {"subject_id": <int>, "reasons": ["<原因标签1>", "<原因标签2>"]}
  ],
  "tasks": [
    {
      "subject_id": <int>,
      "task_type": "error_review|practice|consolidation|lecture",
      "title": "<任务标题>",
      "description": "<任务描述>",
      "knowledge_points": [<kp_id>, ...],
      "sequence": <int>,
      "estimated_minutes": <int>,
      "difficulty": "low|medium|high"
    }
  ],
  "reasoning": "<生成理由>"
}
```

#### 4.2.4 约束条件

| 约束项 | 规则 |
|--------|------|
| 学科数量 | 1-3 门，不平均分配所有学科 |
| 单科时间 | ≥ 15 分钟 |
| 总时间 | 不超过 available_minutes × 1.1 |
| knowledge_point_id | 必须从 knowledge_tree 表中匹配 |
| 输出格式 | 严格 JSON，符合 plan_content JSON Schema |

#### 4.2.5 工具集

| 工具 | 签名 | 说明 |
|------|------|------|
| 获取学情快照 | `get_student_snapshot(student_id: int)` | 返回 profile + knowledge_mastery + subject_risks |
| 获取近期错题 | `get_recent_errors(student_id: int, days: int = 7)` | 返回按学科分组的错题统计 |
| 获取近期考试 | `get_upcoming_exams(student_id: int)` | 返回未来 14 天内的考试安排 |

#### 4.2.6 失败策略

| 失败场景 | 处理策略 |
|---------|----------|
| JSON 解析失败 | 重试 1 次，仍失败则降级到 best 模式 |
| LLM 超时（30s）| 降级到 best 模式重试，仍超时则 generic_fallback |
| best 模式也失败 | 使用 generic_fallback 模板 |
| API key 失效 | 记录日志，使用 generic_fallback |

**generic_fallback 模板**：
```python
def generate_generic_fallback(student_id: int, available_minutes: int) -> dict:
    """
    通用降级计划：按薄弱学科均分时间，任务类型为 consolidation
    """
    weak_subjects = get_weak_subjects(student_id)  # 从 risk_states 获取
    if not weak_subjects:
        weak_subjects = get_all_subjects(student_id)[:3]
    
    num_subjects = min(len(weak_subjects), 3 if available_minutes > 120 else 2 if available_minutes > 60 else 1)
    selected = weak_subjects[:num_subjects]
    time_per_subject = available_minutes // num_subjects
    
    tasks = []
    for i, subject in enumerate(selected):
        tasks.append({
            "subject_id": subject.id,
            "task_type": "consolidation",
            "title": f"{subject.name}基础巩固",
            "description": "复习本周学习内容，巩固基础知识点",
            "knowledge_points": [],
            "sequence": i + 1,
            "estimated_minutes": time_per_subject,
            "difficulty": "medium"
        })
    
    return {
        "recommended_subjects": [{"subject_id": s.id, "reasons": ["通用巩固"]} for s in selected],
        "tasks": tasks,
        "reasoning": "LLM 不可用，使用通用巩固计划"
    }
```

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

#### 4.2.7 模型配置

| 模式 | Provider | Model | 说明 |
|------|----------|-------|------|
| normal | dashscope | qwen-max | 计划生成需要较强推理能力 |
| best | deepseek | deepseek-chat | DeepSeek 在复杂推理上表现优异 |

### 4.3 Tutoring Agent（答疑）

#### 4.3.1 职责定义

实时答疑，引导式教学。根据学生掌握度动态选择教学策略。

#### 4.3.2 触发场景

- `POST /student/qa/chat`（同步）
- `POST /student/qa/chat/stream`（流式 SSE）

#### 4.3.3 System Prompt 模板

```
你是一位耐心的高中学科辅导老师，擅长引导学生思考。

## 教学原则
1. **引导式教学**：不直接给答案（除非策略为 full_solution），优先引导思考
2. **分步讲解**：复杂问题分步骤解答，每步确认学生理解
3. **知识点关联**：回答中自动识别涉及的知识点，输出元数据
4. **追问设计**：每次回答后给出 1-2 个追问，检验理解
5. **错误诊断**：如果学生答错，分析错因（计算/概念/粗心）
6. **LaTeX 格式**：数学公式使用 $...$ 或 $$...$$ 格式

## 教学策略选择（根据学生掌握度）
- **hint**: 知识点状态为"需要巩固"或以上，给出提示引导思考
- **step_by_step**: 知识点状态为"初步接触"，逐步讲解
- **formula**: 涉及公式计算，先列出公式再代入
- **full_solution**: 累计 ≥3 次同知识点问题仍未解决，给出完整解答

## 输入
- student_question: 学生问题
- subject_context: 学科上下文
- session_history: 历史对话
- student_knowledge_status: 学生当前知识点掌握状态（可选）

## 输出格式
在回答的最后，用 ---METADATA--- 分隔符输出元数据：

【正文回答，引导学生思考...】

---METADATA---
knowledge_points: [{"id": <kp_id>, "name": "<知识点名>"}, ...]
strategy: "hint" | "step_by_step" | "formula" | "full_solution"
follow_up_questions: ["<追问1>", "<追问2>"]
error_diagnosis: null | {"type": "<错误类型>", "detail": "<具体说明>"}
---END---

## 示例
学生问题："导数怎么求?"

回答：
很好的问题！导数是微积分的基础概念。让我先问你一个问题：

你知道导数在几何上代表什么意义吗？

---METADATA---
knowledge_points: [{"id": 42, "name": "导数定义"}]
strategy: "hint"
follow_up_questions: ["你知道导数与织给有什么关系吗？", "试试求 f(x)=x² 的导数"]
error_diagnosis: null
---END---
```

#### 4.3.4 约束条件

| 约束项 | 规则 |
|--------|------|
| 教学策略 | 除 full_solution 外，不直接给出完整答案 |
| 元数据分隔符 | 必须以 `---METADATA---` 开始，`---END---` 结束 |
| 知识点 ID | 优先返回 ID，无 ID 时只返回 name，后端匹配 |
| 流式输出 | 元数据部分不推送给前端，仅内部解析 |

#### 4.3.5 工具集

| 工具 | 签名 | 说明 |
|------|------|------|
| 搜索知识点 | `search_knowledge_tree(subject_id: int, keyword: str)` | 模糊搜索知识点，返回匹配结果 |
| 获取学生知识点状态 | `get_student_knowledge_status(student_id: int, kp_id: int)` | 返回指定知识点的掌握状态 |

#### 4.3.6 失败策略

| 失败场景 | 处理策略 |
|---------|----------|
| 流式输出中断 | 返回 SSE error 事件 `{"type":"error","code":"QA_LLM_UNAVAILABLE","message":"..."}` |
| 超时（60s 无新 token）| 中断并返回已生成内容 + error 事件 |
| API key 失效 | 切换 provider（deepseek → anthropic），记录 ModelCallLog.is_fallback=true |
| 元数据解析失败 | 使用默认值（strategy=hint, knowledge_points=[]）|

**SSE 错误事件格式**：
```
event: error
data: {"type": "error", "code": "QA_LLM_UNAVAILABLE", "message": "答疑服务暂时不可用，请稍后重试"}
```

#### 4.3.7 模型配置

| 模式 | Provider | Model | 说明 |
|------|----------|-------|------|
| normal | deepseek | deepseek-chat | 实时答疑需要强对话能力 |
| best | anthropic | claude-sonnet-4-20250514 | Claude 在多轮对话上表现最佳 |

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

#### 4.4.1 职责定义

答疑会话结束后，分析对话质量并更新知识点状态。

#### 4.4.2 触发场景

每次 Tutoring Agent 回答完成后（异步触发，不阻塞用户）。

**触发方式**：
- 同步 chat：在 `chat_sync()` 尾部直接 await
- 流式 chat：在 `save_stream_assistant_message()` 之后，通过 Celery task 异步执行

#### 4.4.3 System Prompt 模板

```
你是一个学情评估分析器。分析答疑会话质量，评估学生知识点掌握情况。

## 输入
- session_id: 会话 ID
- messages: 完整对话历史
- knowledge_points_involved: 本次对话涉及的知识点及当前状态

## 评估规则

### 知识点状态评估标准
- **一次答对**（无提示）: 更强的掌握信号
- **经提示后答对**: 需要巩固信号
- **答错或放弃**: 前项接触或薄弱信号

### 状态迁移建议（LLM 仅建议，最终由规则引擎确认）
- 未观察/初步接触 + 一次答对 → 需要巩固 (升至"基本掌握"需不同会话答对 ≥2 次)
- 未观察/初步接触 + 经提示答对 → 需要巩固
- 任意状态 + 答错 → 初步接触（首次）/ 需要巩固（已接触）
- 需要巩固 + 错题召回答对 → 基本掌握
- 任意状态 + 错题召回答错（累计 ≥2） → 反复失误

## confidence 计算
- 0.9+: 明确证据（多次一致表现）
- 0.7-0.9: 较强信号（单次明确表现）
- 0.5-0.7: 不确定（证据不足）
- <0.5: 不建议更新（证据矛盾或不足）

## 输出格式（严格 JSON，符合 structured_summary 格式）
{
  "knowledge_point_updates": [
    {
      "knowledge_point_id": <int>,
      "knowledge_point_name": "<知识点名>",
      "previous_status": "<当前状态>",
      "new_status": "<建议新状态>",
      "reason": "<迁移原因>",
      "confidence": <0.0-1.0>
    }
  ],
  "session_summary": {
    "total_questions": <int>,
    "correct_first_try": <int>,
    "correct_with_hint": <int>,
    "incorrect": <int>,
    "dominant_error_type": "<主要错误类型>" | null
  },
  "error_book_entries": [
    {
      "subject_id": <int>,
      "question_summary": "<题目摘要>",
      "knowledge_point_ids": [<int>, ...],
      "error_type": "<错误类型>",
      "entry_reason": "wrong" | "not_know" | "repeated_wrong"
    }
  ],
  "suggested_followup": "<后续学习建议>"
}
```

#### 4.4.4 约束条件

| 约束项 | 规则 |
|--------|------|
| previous_status | 必须与数据库当前值一致 |
| confidence 阈值 | <0.7 时不自动更新状态，标记为待人工审核 |
| 单次更新上限 | 一次性更新 >5 个知识点时标记为异常，待审核 |
| LLM 输出 | 仅作为建议，实际迁移由规则引擎确认 |

#### 4.4.5 工具集

| 工具 | 签名 | 说明 |
|------|------|------|
| 获取学生知识点状态 | `get_student_knowledge_status(student_id: int, kp_ids: list[int])` | 批量获取知识点状态 |
| 更新知识点状态 | `update_knowledge_status(student_id: int, kp_id: int, new_status: str, reason: str)` | 更新状态并记录日志 |

#### 4.4.6 失败策略

| 失败场景 | 处理策略 |
|---------|----------|
| 输出格式不合规 | 重试 1 次，仍失败则跳过评估（不更新状态），记录日志 |
| 评估结果异常 | 一次更新 >5 个知识点 → 标记“待人工审核”，不自动写入 |
| LLM 超时 | 不重试，跳过本次评估，记录日志 |
| API 异常 | 降级到 best 模式重试一次，仍失败则跳过 |

#### 4.4.7 状态迁移规则（硬编码，LLM 仅建议）

| 触发 | 当前状态 | 新状态 |
|------|---------|-------|
| 一次答对（无提示） | 未观察/初步接触 | 需要巩固 (*) |
| 经提示后答对 | 未观察/初步接触 | 需要巩固 |
| 答错/放弃 | 任意 | 初步接触（首次）/ 需要巩固（已接触）|
| 错题召回答对 | 需要巩固 | 基本掌握 |
| 错题召回答错（累计≥2） | 任意 | 反复失误 |
| 人工纠偏 | 任意 | 管理员指定 |

(*) 升至“基本掌握”需同一知识点在**不同会话**中答对 ≥ 2 次。

#### 4.4.8 模型配置

| 模式 | Provider | Model | 说明 |
|------|----------|-------|------|
| normal | dashscope | qwen-max | 评估需要分析能力 |
| best | deepseek | deepseek-chat | 深度分析场景 |

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

#### 4.5.1 职责定义

从 OCR 结果中提取结构化题目、识别知识点、判断错题类型。

#### 4.5.2 触发场景

Celery task `process_ocr(upload_id)` 执行时。

**输入**：上传图片的 base64 或 URL。

#### 4.5.3 System Prompt 模板

```
你是一个学习资料识别分析器。从上传的图片中提取题目信息并结构化。

## 任务
1. 识别图片中的所有题目
2. 提取每道题的文本内容和 LaTeX 公式
3. 判断每道题的类型（选择/填空/解答）
4. 推断学科和知识点

## 题目类型定义
- **choice**: 单选/多选题
- **fill_in_blank**: 填空题
- **short_answer**: 简答题
- **calculation**: 计算题
- **proof**: 证明题

## 学科判断
根据题目内容和特征推断学科：
- 数学：含有公式、方程、几何图形
- 物理：含有物理量、单位、实验描述
- 化学：含有化学式、元素符号、反应方程
- 语文：阅读理解、文言文、作文
- 英语：英文文本、语法题

## LaTeX 格式要求
- 数学公式使用 $...$ 或 $$...$$ 包裹
- 保留原始结构，不要简化

## confidence 评分
- 1.0: 完全清晰，100% 确定
- 0.8-0.99: 大部分清晰，少量推断
- 0.6-0.79: 部分模糊，需确认
- <0.6: 识别困难，标记为待人工确认

## 输出格式（严格 JSON）
{
  "detected_subject": "<学科名>",
  "detected_subject_id": <int | null>,
  "questions": [
    {
      "index": <int>,
      "type": "choice|fill_in_blank|short_answer|calculation|proof",
      "content_text": "<纯文本内容>",
      "content_latex": "<含 LaTeX 的内容>",
      "options": ["A. ...", "B. ..."] | null,
      "answer": "<答案>" | null,
      "knowledge_points": ["<知识点名1>", "<知识点名2>"],
      "confidence": <0.0-1.0>
    }
  ],
  "raw_text": "<OCR 全文>",
  "overall_confidence": <0.0-1.0>
}
```

#### 4.5.4 约束条件

| 约束项 | 规则 |
|--------|------|
| knowledge_point_id | 必须从 knowledge_tree 表中匹配，匹配不到时仅返回 name |
| confidence 阈值 | <0.6 的题目标注为“待人工确认” |
| 输出格式 | 严格 JSON，不含多余文本 |
| 图片输入 | 支持 base64 和 URL 两种方式 |

#### 4.5.5 工具集

| 工具 | 签名 | 说明 |
|------|------|------|
| 搜索知识点 | `search_knowledge_tree(subject_id: int, keyword: str)` | 模糊搜索知识点，name → ID 映射 |

#### 4.5.6 失败策略

| 失败场景 | 处理策略 |
|---------|----------|
| JSON 解析失败 | 重试 1 次，仍失败则创建 manual_corrections |
| LLM 超时（30s）| 降级到 best 模式重试 |
| 识别为空 | 标记 ocr_status=failed，创建 manual_corrections |
| Celery 重试耗尽（≤3次）| 创建 manual_corrections(target_type="ocr") |

**失败处理伪代码**：
```python
@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_ocr(self, upload_id: int):
    try:
        result = extraction_agent.extract(upload_id)
        save_ocr_result(upload_id, result, status="completed")
    except ExtractionFailedError as e:
        if self.request.retries < self.max_retries:
            self.retry(exc=e)
        else:
            # 创建人工纠偏记录
            save_ocr_result(upload_id, None, status="failed", error=str(e))
            create_manual_correction(
                target_type="ocr",
                target_id=upload_id,
                original_content=None,
                corrected_content=None,
                correction_reason=f"OCR 失败: {str(e)}"
            )
```

#### 4.5.7 模型配置

| 模式 | Provider | Model | 说明 |
|------|----------|-------|------|
| normal | dashscope | qwen-vl-max | 需要视觉理解能力 |
| best | dashscope | qwen-vl-max | VL 模型两种模式相同（最优质量）|

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

### 5.6 定量化计划生成规则

#### 5.6.1 计划生成核心算法

```python
def generate_daily_plan(student_id: int, learning_mode: str, available_minutes: int) -> dict:
    """
    计划生成核心算法
    
    Args:
        student_id: 学生 ID
        learning_mode: 学习模式 (workday_follow | weekend_review)
        available_minutes: 可用学习时间（分钟）
    
    Returns:
        计划数据（含推荐学科、任务列表、推理说明）
    """
    
    # 1. 计划来源判定
    recent_uploads = get_uploads(student_id, days=1)
    consecutive_no_upload = consecutive_no_upload_days(student_id)
    
    if recent_uploads:
        source = "upload_corrected"
    elif has_history_data(student_id, days=7):
        source = "history_inferred"
    elif consecutive_no_upload >= 7:
        source = "generic_fallback"
    else:
        source = "history_inferred"
    
    # 2. 推荐学科选择（1-3 门）
    if learning_mode == "workday_follow":
        candidates = score_subjects_workday(student_id)
    else:  # weekend_review
        candidates = score_subjects_weekend(student_id)
    
    # 按可用时间确定学科数量
    if available_minutes <= 60:
        num_subjects = 1
    elif available_minutes <= 120:
        num_subjects = 2
    else:
        num_subjects = 3
    
    selected = candidates[:num_subjects]
    
    # 3. 时间分配（按学科得分比例）
    total_score = sum(s.score for s in selected)
    for subject in selected:
        ratio = subject.score / total_score
        subject.allocated_minutes = max(15, int(available_minutes * ratio))
    
    # 确保总时间不超过 available_minutes × 1.1
    total_allocated = sum(s.allocated_minutes for s in selected)
    if total_allocated > available_minutes * 1.1:
        scale_factor = (available_minutes * 1.1) / total_allocated
        for subject in selected:
            subject.allocated_minutes = max(15, int(subject.allocated_minutes * scale_factor))
    
    # 4. 任务类型分配
    tasks = []
    for subject in selected:
        subject_tasks = allocate_task_types(subject, student_id)
        tasks.extend(subject_tasks)
    
    return {
        "source": source,
        "recommended_subjects": selected,
        "tasks": tasks
    }


def score_subjects_workday(student_id: int) -> list[SubjectScore]:
    """
    工作日跟学模式 - 学科评分算法
    
    评分因子及权重：
    - 今日校内同步（有当日上传）：+40
    - 今日错误较多（当日错题 ≥3）：+30
    - 明日任务/测验（upcoming_exams 在 1 天内）：+25
    - 近期反复错误（反复失误知识点 ≥2）：+20
    - 本周覆盖不足（本周该科任务 <2）：+15
    """
    scores = []
    subjects = get_student_subjects(student_id)
    
    for subject in subjects:
        score = 0
        reasons = []
        
        # 因子 1: 今日校内同步
        today_uploads = get_uploads_count(student_id, subject.id, days=0)
        if today_uploads > 0:
            score += 40
            reasons.append("今日校内同步")
        
        # 因子 2: 今日错误较多
        today_errors = get_error_count(student_id, subject.id, days=0)
        if today_errors >= 3:
            score += 30
            reasons.append("今日错误较多")
        
        # 因子 3: 明日任务/测验
        upcoming = get_upcoming_exams(student_id, subject.id, days=1)
        if upcoming:
            score += 25
            reasons.append("明日任务/测验")
        
        # 因子 4: 近期反复错误
        repeated_mistakes = get_repeated_mistake_kps(student_id, subject.id)
        if len(repeated_mistakes) >= 2:
            score += 20
            reasons.append("近期反复错误")
        
        # 因子 5: 本周覆盖不足
        week_tasks = get_week_task_count(student_id, subject.id)
        if week_tasks < 2:
            score += 15
            reasons.append("本周覆盖不足")
        
        scores.append(SubjectScore(subject_id=subject.id, score=score, reasons=reasons))
    
    return sorted(scores, key=lambda x: x.score, reverse=True)


def score_subjects_weekend(student_id: int) -> list[SubjectScore]:
    """
    周末复习模式 - 学科评分算法
    
    评分因子及权重：
    - 本周错题修复（本周新增错题数）：+35
    - 薄弱知识点待修复（反复失误数）：+30
    - 考试临近（upcoming_exams 在 7 天内）：+25
    - 最近成绩下滑（近 2 次成绩环比下降 ≥5%）：+20
    - 本周覆盖不足（本周该科任务 <2）：+15
    """
    scores = []
    subjects = get_student_subjects(student_id)
    
    for subject in subjects:
        score = 0
        reasons = []
        
        # 因子 1: 本周错题修复
        week_errors = get_error_count(student_id, subject.id, days=7)
        score += min(35, week_errors * 5)  # 每题 5 分，上限 35
        if week_errors > 0:
            reasons.append("本周错题修复")
        
        # 因子 2: 薄弱知识点待修复
        weak_kps = get_weak_knowledge_points(student_id, subject.id)  # status in (反复失误, 需要巩固)
        if len(weak_kps) >= 2:
            score += 30
            reasons.append("薄弱知识点待修复")
        
        # 因子 3: 考试临近
        upcoming = get_upcoming_exams(student_id, subject.id, days=7)
        if upcoming:
            score += 25
            reasons.append("考试临近")
        
        # 因子 4: 最近成绩下滑
        score_trend = calculate_score_trend(student_id, subject.id, recent_n=2)
        if score_trend <= -5:  # 下降 5% 以上
            score += 20
            reasons.append("最近成绩下滑")
        
        # 因子 5: 本周覆盖不足
        week_tasks = get_week_task_count(student_id, subject.id)
        if week_tasks < 2:
            score += 15
            reasons.append("本周覆盖不足")
        
        scores.append(SubjectScore(subject_id=subject.id, score=score, reasons=reasons))
    
    return sorted(scores, key=lambda x: x.score, reverse=True)
```

#### 5.6.2 任务强度与类型分配

```python
def determine_task_intensity(student_id: int, subject_id: int) -> str:
    """
    判断任务强度
    
    Returns:
        "high" | "medium" | "low"
    """
    today_qa_count = get_qa_count(student_id, subject_id, days=0)
    today_error_count = get_error_count(student_id, subject_id, days=0)
    today_upload_count = get_uploads_count(student_id, subject_id, days=0)
    
    # 高强度：当日答疑 ≥2 次 或 当日错题 ≥5
    if today_qa_count >= 2 or today_error_count >= 5:
        return "high"
    
    # 中强度：当日有上传 或 当日错题 1-4
    if today_upload_count > 0 or 1 <= today_error_count <= 4:
        return "medium"
    
    # 低强度：无当日活动
    return "low"


def allocate_task_types(subject: SubjectScore, student_id: int) -> list[PlanTask]:
    """
    根据学情分配任务类型
    
    任务类型分配比例：
    - error_review: 有未召回错题时优先（30-50%）
    - practice: 有新上传内容时（20-40%）
    - consolidation: 需要巩固的知识点（20-30%）
    - lecture: 首次接触的知识点（10-20%）
    """
    tasks = []
    remaining_minutes = subject.allocated_minutes
    sequence = 1
    
    # 1. error_review - 优先安排错题复习
    unreached_errors = get_unreached_errors(student_id, subject.subject_id, limit=5)
    if unreached_errors:
        error_minutes = min(remaining_minutes * 0.5, len(unreached_errors) * 6)  # 每题约 6 分钟
        tasks.append(PlanTask(
            subject_id=subject.subject_id,
            task_type="error_review",
            title=f"{subject.name}错题回顾",
            knowledge_points=[e.knowledge_point_id for e in unreached_errors],
            sequence=sequence,
            estimated_minutes=int(error_minutes),
            difficulty="medium"
        ))
        remaining_minutes -= error_minutes
        sequence += 1
    
    # 2. practice - 新上传内容练习
    recent_uploads = get_recent_uploads(student_id, subject.subject_id, days=1)
    if recent_uploads and remaining_minutes > 15:
        practice_minutes = min(remaining_minutes * 0.4, 30)
        tasks.append(PlanTask(
            subject_id=subject.subject_id,
            task_type="practice",
            title=f"{subject.name}同步练习",
            knowledge_points=extract_kps_from_uploads(recent_uploads),
            sequence=sequence,
            estimated_minutes=int(practice_minutes),
            difficulty="medium"
        ))
        remaining_minutes -= practice_minutes
        sequence += 1
    
    # 3. consolidation - 需巩固知识点
    weak_kps = get_weak_knowledge_points(student_id, subject.subject_id)[:3]
    if weak_kps and remaining_minutes > 15:
        tasks.append(PlanTask(
            subject_id=subject.subject_id,
            task_type="consolidation",
            title=f"{subject.name}知识点巩固",
            knowledge_points=[kp.id for kp in weak_kps],
            sequence=sequence,
            estimated_minutes=int(remaining_minutes),
            difficulty="low"
        ))
    
    return tasks
```

### 5.7 错题召回优先级队列设计

#### 5.7.1 召回优先级评分公式

```
priority_score = status_weight           # 知识点状态权重
               + recency_weight          # 时间衰减权重
               + importance_weight       # 知识点重要性权重
               - recall_penalty          # 已召回惩罚
```

#### 5.7.2 各因子计算规则

| 因子 | 计算方式 | 分值范围 |
|------|---------|----------|
| `status_weight` | 反复失误=50, 需要巩固=30, 初步接触=20, 其他=0 | 0-50 |
| `recency_weight` | 30 × e^(-days_since_last_error / 14) | 0-30 |
| `importance_weight` | 20 × importance_score | 0-20 |
| `recall_penalty` | 10 × recall_count（已成功召回次数） | 0-∞ |

#### 5.7.3 SQL 实现

```sql
-- 错题召回优先级队列查询
SELECT 
    eb.id,
    eb.question_content,
    eb.knowledge_points,
    eb.subject_id,
    eb.error_type,
    eb.recall_count,
    eb.created_at,
    -- 计算优先级分数
    CASE sks.status
        WHEN '反复失误' THEN 50
        WHEN '需要巩固' THEN 30
        WHEN '初步接触' THEN 20
        ELSE 0
    END
    + 30 * EXP(-EXTRACT(EPOCH FROM (NOW() - eb.created_at)) / (14 * 86400))
    + 20 * COALESCE(kt.importance_score, 0.5)
    - 10 * COALESCE(eb.recall_count, 0)
    AS priority_score
FROM error_book eb
-- 关联学生知识点状态（取错题关联的第一个知识点）
LEFT JOIN student_knowledge_status sks 
    ON sks.student_id = eb.student_id 
    AND sks.knowledge_point_id = (eb.knowledge_points->0)::int
-- 关联知识树获取重要性分数
LEFT JOIN knowledge_tree kt 
    ON kt.id = (eb.knowledge_points->0)::int
WHERE 
    eb.student_id = :student_id
    AND eb.is_recalled = false
    AND eb.is_deleted = false
    AND COALESCE(eb.recall_count, 0) < 3  -- 已成功召回 ≥3 次的题目排除
ORDER BY priority_score DESC
LIMIT :batch_size;
```

#### 5.7.4 召回批次规则

| 规则 | 说明 |
|------|------|
| 单次召回上限 | 20 题 |
| 同一知识点上限 | 最多选 3 题（避免重复训练） |
| 自动排除条件 | 已成功召回 ≥3 次 |
| 优先级更新时机 | 每次召回结果记录后重新计算 |

```python
def get_recall_batch(student_id: int, batch_size: int = 20) -> list[ErrorBookEntry]:
    """
    获取错题召回批次
    
    规则：
    1. 按优先级分数降序排列
    2. 同一知识点最多选 3 题
    3. 已成功召回 ≥3 次的题目自动排除
    """
    raw_results = execute_priority_query(student_id, limit=batch_size * 2)
    
    selected = []
    kp_count = defaultdict(int)
    
    for entry in raw_results:
        if len(selected) >= batch_size:
            break
        
        # 检查同一知识点数量限制
        primary_kp = entry.knowledge_points[0] if entry.knowledge_points else None
        if primary_kp and kp_count[primary_kp] >= 3:
            continue
        
        selected.append(entry)
        if primary_kp:
            kp_count[primary_kp] += 1
    
    return selected
```

### 5.8 答疑质量评估指标

#### 5.8.1 质量评估指标定义

| 指标 | 计算方式 | 阈值说明 |
|------|---------|----------|
| `first_try_rate` | correct_first_try / total_questions | <0.2 为"差" |
| `hint_dependency` | correct_with_hint / (correct_first_try + correct_with_hint) | >0.8 为"过度依赖提示" |
| `session_resolution` | 会话是否最终解决问题（最后一轮答对） | false 为"未解决" |
| `knowledge_regression` | 本次会话是否出现知识点状态降级 | true 为"退步" |
| `follow_up_rate` | 会话后 24h 内是否有同知识点的后续答疑 | true 为"重复困扰" |

#### 5.8.2 自动触发人工纠偏的条件

| 序号 | 触发条件 | 处理动作 |
|------|---------|----------|
| 1 | **连续 3 次答疑同一知识点，first_try_rate < 0.2** | 创建 `manual_corrections(target_type='qa')` 记录，建议检查 Tutoring Agent 教学策略 |
| 2 | **Assessment Agent confidence < 0.5** | 评估结果不自动写入，标记为待人工审核 |
| 3 | **学生 24h 内对同一知识点发起 ≥3 次答疑** | 创建纠偏记录，同时提高该知识点在 Planning Agent 中的优先级 |
| 4 | **单次会话 knowledge_regression = true 且涉及 ≥2 个知识点** | 标记为"答疑质量异常"，等待管理员审核 |

```python
def check_qa_quality_triggers(session_id: int, student_id: int) -> list[QualityAlert]:
    """
    检查答疑质量，触发人工纠偏条件
    """
    alerts = []
    session = get_session(session_id)
    summary = session.structured_summary
    
    # 条件 1: 连续低正确率
    kp_ids = extract_knowledge_points(session)
    for kp_id in kp_ids:
        recent_sessions = get_recent_sessions_for_kp(student_id, kp_id, count=3)
        if len(recent_sessions) >= 3:
            avg_first_try_rate = calculate_avg_first_try_rate(recent_sessions)
            if avg_first_try_rate < 0.2:
                alerts.append(QualityAlert(
                    type="low_first_try_rate",
                    target_type="qa",
                    target_id=session_id,
                    reason=f"知识点 {kp_id} 连续 3 次答疑正确率过低 ({avg_first_try_rate:.0%})",
                    suggested_action="检查 Tutoring Agent 教学策略是否适当"
                ))
    
    # 条件 2: Assessment confidence 过低
    if summary and summary.get("confidence", 1.0) < 0.5:
        alerts.append(QualityAlert(
            type="low_confidence",
            target_type="qa",
            target_id=session_id,
            reason=f"Assessment 置信度过低 ({summary.get('confidence'):.2f})",
            suggested_action="评估结果待人工审核"
        ))
    
    # 条件 3: 同知识点高频答疑
    for kp_id in kp_ids:
        recent_count = count_sessions_for_kp_in_hours(student_id, kp_id, hours=24)
        if recent_count >= 3:
            alerts.append(QualityAlert(
                type="high_frequency",
                target_type="qa",
                target_id=session_id,
                reason=f"知识点 {kp_id} 24h 内答疑 {recent_count} 次",
                suggested_action="提高该知识点计划优先级"
            ))
    
    # 条件 4: 知识点退步
    if summary:
        regressions = [u for u in summary.get("knowledge_point_updates", []) 
                       if is_regression(u["previous_status"], u["new_status"])]
        if len(regressions) >= 2:
            alerts.append(QualityAlert(
                type="knowledge_regression",
                target_type="qa",
                target_id=session_id,
                reason=f"单次会话 {len(regressions)} 个知识点退步",
                suggested_action="答疑质量异常，待管理员审核"
            ))
    
    # 批量创建 manual_corrections
    for alert in alerts:
        create_manual_correction(
            target_type=alert.target_type,
            target_id=alert.target_id,
            original_content={"alert_type": alert.type},
            corrected_content=None,
            correction_reason=alert.reason
        )
    
    return alerts
```

### 5.9 LangGraph 多 Agent 编排设计

> **说明**：当前 MVP 阶段（5 学生）采用 Python 函数调用 + Celery 异步任务实现 Agent 编排，
> 未引入 LangGraph。以下为未来扩展时的参考设计。

#### 5.9.1 工作流状态定义

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal

class StudyPilotState(TypedDict):
    """工作流共享状态"""
    student_id: int
    session_id: int | None
    messages: list[dict]
    intent: str | None            # Routing Agent 输出
    extracted_data: dict | None   # Extraction Agent 输出
    tutoring_response: str | None # Tutoring Agent 输出
    assessment: dict | None       # Assessment Agent 输出
    plan: dict | None             # Planning Agent 输出
    errors: list[str]             # 错误收集
```

#### 5.9.2 答疑工作流定义

```python
def create_qa_workflow() -> StateGraph:
    """
    答疑工作流：Routing → Tutoring → Assessment
    """
    workflow = StateGraph(StudyPilotState)
    
    # 添加节点
    workflow.add_node("routing", routing_agent_node)
    workflow.add_node("tutoring", tutoring_agent_node)
    workflow.add_node("assessment", assessment_agent_node)
    
    # 设置入口
    workflow.set_entry_point("routing")
    
    # 路由条件
    def route_by_intent(state: StudyPilotState) -> Literal["tutoring", "end"]:
        intent = state.get("intent")
        if intent in ("ask", "follow_up", "upload_question"):
            return "tutoring"
        return "end"  # chat, operate 直接结束
    
    workflow.add_conditional_edges(
        "routing",
        route_by_intent,
        {
            "tutoring": "tutoring",
            "end": END,
        }
    )
    
    # 顺序边
    workflow.add_edge("tutoring", "assessment")
    workflow.add_edge("assessment", END)
    
    return workflow.compile()

# 单例实例
qa_workflow = create_qa_workflow()
```

#### 5.9.3 上传处理工作流定义

```python
def create_upload_workflow() -> StateGraph:
    """
    上传处理工作流：Extraction → (可选) Planning
    """
    workflow = StateGraph(StudyPilotState)
    
    workflow.add_node("extraction", extraction_agent_node)
    workflow.add_node("planning", planning_agent_node)
    
    workflow.set_entry_point("extraction")
    
    # 提取成功后可选触发计划更新
    def should_update_plan(state: StudyPilotState) -> Literal["planning", "end"]:
        if state.get("extracted_data") and not state.get("errors"):
            # 今日尚无计划时触发生成
            if not has_today_plan(state["student_id"]):
                return "planning"
        return "end"
    
    workflow.add_conditional_edges(
        "extraction",
        should_update_plan,
        {
            "planning": "planning",
            "end": END,
        }
    )
    
    workflow.add_edge("planning", END)
    
    return workflow.compile()

upload_workflow = create_upload_workflow()
```

#### 5.9.4 Agent 节点实现示例

```python
async def routing_agent_node(state: StudyPilotState) -> StudyPilotState:
    """
    Routing Agent 节点
    """
    try:
        result = await routing_agent.classify(
            message=state["messages"][-1]["content"],
            has_attachments=bool(state["messages"][-1].get("attachments")),
            session_context="existing_session" if state.get("session_id") else "new_session"
        )
        state["intent"] = result["intent"]
    except Exception as e:
        state["errors"].append(f"Routing failed: {str(e)}")
        state["intent"] = "ask"  # 默认路由
    
    return state


async def tutoring_agent_node(state: StudyPilotState) -> StudyPilotState:
    """
    Tutoring Agent 节点（同步版本，流式需单独处理）
    """
    try:
        response, metadata = await tutoring_agent.respond(
            student_id=state["student_id"],
            messages=state["messages"],
            intent=state["intent"]
        )
        state["tutoring_response"] = response
        state["messages"].append({"role": "assistant", "content": response})
    except Exception as e:
        state["errors"].append(f"Tutoring failed: {str(e)}")
    
    return state


async def assessment_agent_node(state: StudyPilotState) -> StudyPilotState:
    """
    Assessment Agent 节点
    """
    try:
        assessment = await assessment_agent.evaluate(
            session_id=state["session_id"],
            messages=state["messages"]
        )
        state["assessment"] = assessment
        
        # 应用评估结果（规则验证后）
        await apply_assessment_results(state["student_id"], assessment)
    except Exception as e:
        state["errors"].append(f"Assessment failed: {str(e)}")
    
    return state
```

#### 5.9.5 工作流调用示例

```python
async def handle_qa_message(student_id: int, session_id: int, message: str) -> dict:
    """
    处理答疑消息（使用 LangGraph 工作流）
    """
    initial_state = StudyPilotState(
        student_id=student_id,
        session_id=session_id,
        messages=[{"role": "user", "content": message}],
        intent=None,
        extracted_data=None,
        tutoring_response=None,
        assessment=None,
        plan=None,
        errors=[]
    )
    
    # 执行工作流
    final_state = await qa_workflow.ainvoke(initial_state)
    
    return {
        "response": final_state["tutoring_response"],
        "intent": final_state["intent"],
        "assessment": final_state["assessment"],
        "errors": final_state["errors"]
    }
```

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
