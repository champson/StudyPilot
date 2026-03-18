# AI高考伴学教练 核心架构设计与技术方案

基于《AI高考伴学教练 PRD (MVP 需求完善版)》与确认的技术选型，本文档定义系统核心架构设计与技术实施方案。

---

## 1. 技术栈总览

### 1.1 技术选型总览表

| 层次 | 选型 | 版本 | 用途 |
|------|------|------|------|
| **前端框架** | Next.js (App Router) | 14+ | 学生端/家长端 H5/Web |
| **前端样式** | TailwindCSS | 3.x | 原子化 CSS |
| **前端语言** | TypeScript | 5.x | 类型安全 |
| **后端框架** | FastAPI | 0.110+ | 异步 API 服务 |
| **后端语言** | Python | 3.11+ | 服务端开发 |
| **数据库** | PostgreSQL | 15+ | 主数据存储 (JSONB) |
| **ORM** | SQLAlchemy | 2.0+ | 异步数据库访问 |
| **缓存** | Redis | 7.x | 缓存/会话/队列 |
| **异步任务** | Celery | 5.x | 后台任务处理 |
| **Agent 编排** | LangGraph | 0.1+ | Multi-Agent 工作流 |
| **LLM SDK** | LangChain + 各厂商 SDK | - | 大模型调用 |
| **数据验证** | Pydantic | V2 | 请求/响应校验 |
| **对象存储** | 阿里云 OSS | - | 图片/文件存储 |
| **云平台** | 阿里云 | - | 部署与基础设施 |
| **代码质量 (Python)** | Ruff | 0.3+ | Lint + Format |
| **代码质量 (前端)** | ESLint + Prettier | - | Lint + Format |

### 1.2 首期成本估算表（月度）

| 资源类型 | 规格 | 预估费用（元/月） | 备注 |
|---------|------|------------------|------|
| **云服务器 ECS** | 2核4G × 2 | 400 | API + Worker |
| **RDS PostgreSQL** | 1核2G 基础版 | 200 | 首期 5 用户足够 |
| **Redis** | 1G 标准版 | 100 | 缓存与队列 |
| **OSS** | 50GB | 10 | 图片存储 |
| **LLM 调用（正常效果模式）** | - | 500-1000 | 以国产模型为主 |
| **LLM 调用（最优效果模式）** | - | 2000-3000 | GPT-4o/Claude 成本更高 |
| **域名 + SSL** | - | 10 | 基础配置 |
| **合计（正常效果模式）** | - | **~1200** | 日常运行 |
| **合计（最优效果模式）** | - | **~3700** | 效果优先 |

---

## 2. 系统架构总览

### 2.1 分层架构描述

系统采用经典的分层架构，从上到下依次为：

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端层 (Next.js)                          │
│   学生工作台 | 家长报告页 | 分享链接页 | 管理后台                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API/BFF 层 (FastAPI)                          │
│   /student/* | /parent/* | /share/* | /admin/*                  │
│   认证鉴权 | 请求校验 | 响应格式化 | 限流                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                Agent 编排层 (LangGraph)                          │
│   Routing Agent → Planning Agent → Tutoring Agent               │
│                         ↓                                        │
│               Assessment Agent ← Extraction Agent                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     大模型服务层                                   │
│   ModelRouter → 正常效果模型 | 最优效果模型 | Fallback              │
│   Qwen | DeepSeek | Claude | GPT-4o                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     数据持久化层                                   │
│   PostgreSQL (JSONB) | Redis (Cache/Queue) | OSS (Objects)      │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 各层职责

| 层次 | 职责 | 关键组件 |
|------|------|---------|
| **前端层** | 用户界面渲染、交互处理、实时状态展示 | Next.js App Router, TailwindCSS |
| **API/BFF 层** | 请求路由、认证鉴权、数据聚合、响应格式化 | FastAPI, Pydantic |
| **Agent 编排层** | 多 Agent 协作流程控制、状态机管理 | LangGraph, LangChain |
| **大模型服务层** | 模型路由、调用封装、降级处理、日志记录 | ModelRouter, 各厂商 SDK |
| **数据持久化层** | 数据存储、缓存、文件存储 | PostgreSQL, Redis, OSS |

### 2.3 核心数据流向

1. **学生请求** → 前端 → API 网关 → 认证中间件 → 业务路由
2. **计划生成** → Planning Agent → ModelRouter → LLM → 结构化输出 → 数据库
3. **答疑流程** → Routing Agent → Tutoring Agent → 流式响应 → Assessment Agent → 状态更新
4. **学情更新** → Event 抛出 → Redis Queue → Celery Worker → 异步汇总

---

## 3. Agent 多模型可配置架构

### 3.1 双模式设计（正常效果 / 最优效果）

系统支持两种运行模式，由管理员通过管理接口手动切换，切换后影响所有 Agent 的模型选择：

**模式定义**：

| 模式 | 定位 | 适用场景 |
|------|------|---------|
| **正常效果模式 (normal)** | 成本优先，延迟较低 | 日常学习、常规使用 |
| **最优效果模式 (best)** | 效果优先，质量最佳 | 重要答疑、效果验证 |

**各 Agent 模型映射表**：

| Agent | 正常效果模型 | 最优效果模型 | 核心用途 |
|-------|-------------|-------------|---------|
| **Extraction Agent** | Qwen-VL-Max | GPT-4o | 图文识别、题目结构化、LaTeX 提取 |
| **Planning Agent** | Qwen-Max | DeepSeek V3 | 学科优先级、每日任务流生成 |
| **Tutoring Agent** | DeepSeek V3 | Claude 3.5 Sonnet | 实时答疑、多轮对话引导 |
| **Assessment Agent** | Qwen-Turbo | DeepSeek V3 | 知识点状态变更、学情评估 |
| **Routing Agent** | Qwen-Turbo | Qwen-Turbo | 意图识别、对话分类（两种模式相同） |

### 3.2 模型配置体系

#### 3.2.1 YAML 配置结构

配置文件路径: `config/model_config.yaml`

```yaml
# 当前运行模式: normal | best
current_mode: normal

# 各 Agent 的模型配置
agents:
  extraction:
    normal:
      provider: qwen
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
      provider: qwen
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
      model: claude-3-5-sonnet-20241022
      timeout: 60
      max_retries: 2
      temperature: 0.7
      stream: true

  assessment:
    normal:
      provider: qwen
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

  routing:
    normal:
      provider: qwen
      model: qwen-turbo
      timeout: 10
      max_retries: 1
      temperature: 0.0
    best:
      provider: qwen
      model: qwen-turbo
      timeout: 10
      max_retries: 1
      temperature: 0.0

# Provider 配置
providers:
  qwen:
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: DASHSCOPE_API_KEY
  deepseek:
    base_url: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
  anthropic:
    base_url: https://api.anthropic.com
    api_key_env: ANTHROPIC_API_KEY
  openai:
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
```

#### 3.2.2 ModelRouter 路由逻辑

```python
# app/llm/model_router.py

from enum import Enum
from typing import Optional, AsyncGenerator
from pydantic import BaseModel
import yaml
import asyncio
from datetime import datetime

class RunMode(str, Enum):
    NORMAL = "normal"
    BEST = "best"

class ModelConfig(BaseModel):
    provider: str
    model: str
    timeout: int = 30
    max_retries: int = 2
    temperature: float = 0.7
    stream: bool = False

class ModelCallLog(BaseModel):
    agent_name: str
    mode: RunMode
    provider: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    is_fallback: bool
    success: bool
    error_message: Optional[str] = None
    estimated_cost: float
    timestamp: datetime

class ModelRouter:
    """
    模型路由器：根据当前模式选择对应模型，支持自动降级。

    当前模式存储在 Redis（key: system:run_mode），所有进程（API / Worker / Beat）
    统一从 Redis 读取，确保 switch_mode() 后所有进程即时感知，无需重启。
    YAML 文件仅作为初始默认值来源（当 Redis 中尚无值时回退读取）。
    """

    REDIS_MODE_KEY = "system:run_mode"

    def __init__(self, config_path: str = "config/model_config.yaml", redis_client=None):
        self._config = self._load_config(config_path)
        self._redis = redis_client  # 由外部注入（FastAPI lifespan / Celery setup）
        self._providers = {}  # 缓存 provider 客户端

    def _load_config(self, path: str) -> dict:
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    @property
    def current_mode(self) -> RunMode:
        """从 Redis 读取当前模式；Redis 不可用时回退到 YAML 默认值"""
        if self._redis:
            try:
                val = self._redis.get(self.REDIS_MODE_KEY)
                if val:
                    return RunMode(val.decode() if isinstance(val, bytes) else val)
            except Exception:
                pass
        return RunMode(self._config.get("current_mode", "normal"))

    def switch_mode(self, mode: RunMode) -> None:
        """切换运行模式（写入 Redis，所有进程实时生效，无需重启）"""
        if self._redis:
            self._redis.set(self.REDIS_MODE_KEY, mode.value)
        # 同时更新 YAML 文件作为持久化备份
        self._config["current_mode"] = mode.value
        with open("config/model_config.yaml", 'w') as f:
            yaml.dump(self._config, f)

    def get_model_config(self, agent_name: str, mode: Optional[RunMode] = None) -> ModelConfig:
        """获取指定 Agent 在指定模式下的模型配置"""
        mode = mode or self._current_mode
        agent_config = self._config["agents"][agent_name][mode.value]
        return ModelConfig(**agent_config)
    
    def get_fallback_config(self, agent_name: str) -> ModelConfig:
        """获取降级配置（使用另一模式的模型）"""
        fallback_mode = RunMode.BEST if self._current_mode == RunMode.NORMAL else RunMode.NORMAL
        return self.get_model_config(agent_name, fallback_mode)
    
    async def invoke(
        self,
        agent_name: str,
        messages: list[dict],
        **kwargs
    ) -> tuple[str, ModelCallLog]:
        """
        调用模型，自动处理降级
        返回: (响应内容, 调用日志)
        """
        config = self.get_model_config(agent_name)
        start_time = datetime.now()
        
        try:
            response = await self._call_model(config, messages, **kwargs)
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            log = self._create_log(
                agent_name=agent_name,
                config=config,
                latency_ms=int(latency),
                response=response,
                is_fallback=False
            )
            return response["content"], log
            
        except Exception as e:
            # 降级到另一模式
            fallback_config = self.get_fallback_config(agent_name)
            start_time = datetime.now()
            
            try:
                response = await self._call_model(fallback_config, messages, **kwargs)
                latency = (datetime.now() - start_time).total_seconds() * 1000
                
                log = self._create_log(
                    agent_name=agent_name,
                    config=fallback_config,
                    latency_ms=int(latency),
                    response=response,
                    is_fallback=True,
                    original_error=str(e)
                )
                return response["content"], log
                
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Both primary and fallback models failed. "
                    f"Primary: {e}, Fallback: {fallback_error}"
                )
    
    async def invoke_stream(
        self,
        agent_name: str,
        messages: list[dict],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式调用模型"""
        config = self.get_model_config(agent_name)
        async for chunk in self._call_model_stream(config, messages, **kwargs):
            yield chunk
```

### 3.3 模型调用日志与监控

#### 3.3.1 调用日志字段定义

所有模型调用记录存储于 `model_call_logs` 表：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | BIGSERIAL | 主键 |
| `agent_name` | VARCHAR(50) | Agent 名称 |
| `mode` | VARCHAR(10) | 运行模式 (normal/best) |
| `provider` | VARCHAR(50) | 模型提供商 |
| `model` | VARCHAR(100) | 模型名称 |
| `latency_ms` | INTEGER | 响应延迟（毫秒）|
| `input_tokens` | INTEGER | 输入 token 数 |
| `output_tokens` | INTEGER | 输出 token 数 |
| `is_fallback` | BOOLEAN | 是否为降级调用 |
| `success` | BOOLEAN | 是否成功 |
| `error_message` | TEXT | 错误信息 |
| `estimated_cost` | DECIMAL(10,6) | 估算成本（元）|
| `request_id` | UUID | 关联请求 ID |
| `student_id` | INTEGER | 关联学生 ID |
| `created_at` | TIMESTAMPTZ | 创建时间 |

#### 3.3.2 成本追踪

```python
# 各模型价格配置（元/1K tokens）
MODEL_PRICING = {
    "qwen-vl-max": {"input": 0.02, "output": 0.02},
    "qwen-max": {"input": 0.02, "output": 0.06},
    "qwen-turbo": {"input": 0.002, "output": 0.006},
    "deepseek-chat": {"input": 0.001, "output": 0.002},
    "claude-3-5-sonnet-20241022": {"input": 0.021, "output": 0.105},
    "gpt-4o": {"input": 0.035, "output": 0.105},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """计算单次调用成本"""
    pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000
```

---

## 4. Multi-Agent 编排设计（LangGraph）

### 4.1 Agent 职责定义

| Agent | 输入 | 输出 | 职责边界 |
|-------|------|------|---------|
| **Routing Agent** | 用户原始输入 | 意图分类 + 路由目标 | 识别用户意图（上传题目/答疑/闲聊/操作），将请求路由到对应 Agent |
| **Extraction Agent** | 图片/文本 | 结构化题目数据 | OCR 识别、LaTeX 提取、题目结构化、学科/知识点初判 |
| **Planning Agent** | 学情快照 + 模式 + 时间 | 今日计划 JSON | 基于学情和模式规则生成 1-3 门学科的任务流与推荐标签 |
| **Tutoring Agent** | 题目上下文 + 学生问题 | 分步讲解/提示 | 多轮对话答疑、引导式教学、不直接给答案 |
| **Assessment Agent** | 答疑/做题结果 | 知识点状态事件 | 评估学习效果、生成状态变更事件 |

### 4.2 每日学习规划流

#### 4.2.1 完整数据流

```
学生进入工作台
        │
        ▼
┌───────────────────┐
│ 1. 加载学情快照    │  ← student_profile_snapshots 表
│    StudentProfile │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 2. 确定学习模式    │  ← 系统推荐 + 学生可改选
│    WorkdayFollow  │     工作日默认跟学
│    WeekendReview  │     周末默认复习
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 3. 收集可用时间    │  ← 学生输入
│    available_time │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 4. 检查新上传内容  │  ← study_uploads 表
│    Extraction     │     若有新上传触发 OCR
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 5. 规则引擎粗排    │  ← 按模式内优先级规则
│    RuleEngine     │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 6. Planning Agent │  ← LLM 生成最终计划
│    生成任务流      │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 7. 存储计划并返回  │  → daily_plans + plan_tasks
└───────────────────┘
```

#### 4.2.2 两种学习模式的路由逻辑

```python
# app/agents/planning/mode_router.py

from enum import Enum
from datetime import date

class LearningMode(str, Enum):
    WORKDAY_FOLLOW = "workday_follow"   # 工作日跟学
    WEEKEND_REVIEW = "weekend_review"   # 周末复习

class PriorityFactor(str, Enum):
    # 工作日模式因素
    TODAY_SCHOOL_SYNC = "今日校内同步"
    TODAY_ERRORS_HIGH = "今日错误较多"
    TOMORROW_TASK = "明日任务/测验"
    RECENT_REPEAT_ERRORS = "近期反复错误"
    COVERAGE_COMPENSATION = "本周覆盖不足"
    
    # 周末模式因素
    WEEK_ERROR_FIX = "本周错题修复"
    HIGH_RISK_KNOWLEDGE = "薄弱知识点待修复"
    EXAM_APPROACHING = "考试临近"
    RECENT_SCORE_DROP = "最近成绩下滑"

def get_default_mode(current_date: date) -> LearningMode:
    """根据日期推荐默认模式"""
    # 周六=5, 周日=6
    if current_date.weekday() >= 5:
        return LearningMode.WEEKEND_REVIEW
    return LearningMode.WORKDAY_FOLLOW

def get_priority_rules(mode: LearningMode) -> list[PriorityFactor]:
    """获取模式内优先级规则"""
    if mode == LearningMode.WORKDAY_FOLLOW:
        return [
            PriorityFactor.TODAY_SCHOOL_SYNC,
            PriorityFactor.TODAY_ERRORS_HIGH,
            PriorityFactor.TOMORROW_TASK,
            PriorityFactor.RECENT_REPEAT_ERRORS,
            PriorityFactor.COVERAGE_COMPENSATION,
        ]
    else:  # WEEKEND_REVIEW
        return [
            PriorityFactor.WEEK_ERROR_FIX,
            PriorityFactor.HIGH_RISK_KNOWLEDGE,
            PriorityFactor.EXAM_APPROACHING,
            PriorityFactor.COVERAGE_COMPENSATION,
        ]

def determine_subject_count(available_minutes: int, task_intensity: str) -> int:
    """
    确定推荐学科数量
    task_intensity: high/medium/low
    """
    if available_minutes < 30 or task_intensity == "high":
        return 1
    elif available_minutes < 60:
        return 2
    else:
        return 3 if task_intensity == "low" else 2
```

#### 4.2.3 推断与降级机制

```python
# app/agents/planning/fallback.py

async def generate_plan_with_fallback(
    student_id: int,
    mode: LearningMode,
    available_minutes: int,
    new_uploads: list | None,
    db: AsyncSession
) -> DailyPlan:
    """
    生成计划，支持降级
    """
    # 获取学情快照
    snapshot = await get_latest_snapshot(student_id, db)
    
    # 检查是否有足够的输入
    has_today_input = new_uploads and len(new_uploads) > 0
    consecutive_no_input_days = await count_no_input_days(student_id, db)
    
    plan_source = PlanSource.UPLOAD_CORRECTED if has_today_input else PlanSource.HISTORY_INFERRED
    
    # 连续 7 天无输入，降级为通用补漏计划
    if consecutive_no_input_days >= 7:
        plan_source = PlanSource.GENERIC_FALLBACK
        return await generate_generic_fallback_plan(
            student_id=student_id,
            mode=mode,
            available_minutes=available_minutes,
            warning="连续7天未上传新内容，建议补充上传以恢复个性化准确度"
        )
    
    # 调用 Planning Agent 生成计划
    plan = await planning_agent.generate(
        snapshot=snapshot,
        mode=mode,
        available_minutes=available_minutes,
        new_uploads=new_uploads,
    )
    
    # 标记计划来源
    plan.source = plan_source
    plan.is_history_inferred = not has_today_input
    
    return plan
```

### 4.3 实时答疑流

#### 4.3.1 答疑流转设计

```
用户发送消息/上传题目
            │
            ▼
    ┌───────────────┐
    │ Routing Agent │  意图识别
    └───────┬───────┘
            │
    ┌───────┴───────┬────────────┐
    │               │            │
    ▼               ▼            ▼
┌───────┐    ┌───────────┐   ┌──────┐
│ 上传  │    │ 答疑/追问 │   │ 闲聊 │
│ 题目  │    │           │   │ 拦截 │
└───┬───┘    └─────┬─────┘   └──────┘
    │              │
    ▼              │
┌──────────────┐   │
│ Extraction   │   │
│ Agent (OCR)  │   │
└──────┬───────┘   │
       │           │
       └─────┬─────┘
             ▼
    ┌─────────────────┐
    │ Tutoring Agent  │  多轮答疑
    │ (流式响应)       │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Assessment Agent│  效果评估
    │ (异步触发)       │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 状态变更事件     │  → Redis → Celery
    │ KnowledgeEvent  │
    └─────────────────┘
```

#### 4.3.2 LangGraph 工作流定义

```python
# app/agents/workflows/tutoring_workflow.py

from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal

class TutoringState(TypedDict):
    student_id: int
    session_id: str
    messages: list[dict]
    current_question: dict | None
    intent: str | None
    extracted_content: dict | None
    tutoring_response: str | None
    assessment_event: dict | None

def create_tutoring_workflow() -> StateGraph:
    workflow = StateGraph(TutoringState)
    
    # 添加节点
    workflow.add_node("routing", routing_agent_node)
    workflow.add_node("extraction", extraction_agent_node)
    workflow.add_node("tutoring", tutoring_agent_node)
    workflow.add_node("assessment", assessment_agent_node)
    
    # 设置入口
    workflow.set_entry_point("routing")
    
    # 路由逻辑
    def route_by_intent(state: TutoringState) -> Literal["extraction", "tutoring", "end"]:
        intent = state.get("intent")
        if intent == "upload_question":
            return "extraction"
        elif intent in ("ask_question", "follow_up"):
            return "tutoring"
        else:
            return "end"
    
    workflow.add_conditional_edges(
        "routing",
        route_by_intent,
        {
            "extraction": "extraction",
            "tutoring": "tutoring",
            "end": END,
        }
    )
    
    # extraction 后进入 tutoring
    workflow.add_edge("extraction", "tutoring")
    
    # tutoring 后进入 assessment
    workflow.add_edge("tutoring", "assessment")
    
    # assessment 结束
    workflow.add_edge("assessment", END)
    
    # 引入 Checkpointer 进行多轮对话状态持久化 (防服务重启丢失上下文)
    # 实际实现可传入 AsyncpgSaver 或 RedisSaver
    # return workflow.compile(checkpointer=checkpointer)
    return workflow.compile()

# 单例工作流实例
tutoring_graph = create_tutoring_workflow()
```

#### 4.3.3 流式响应设计

```python
# app/api/routes/student.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/student")

@router.post("/qa/chat/stream")
async def chat_stream(
    request: ChatRequest,
    student: Student = Depends(get_current_student),
):
    """流式答疑接口"""
    async def generate():
        try:
            async for chunk in tutoring_agent.stream_response(
                student_id=student.id,
                session_id=request.session_id,
                message=request.message,
                attachments=request.attachments,
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            # 推流异常处理：发送错误特征帧以便前端捕获并降级
            import json
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

### 4.4 学情状态更新流

#### 4.4.1 实时更新（Event Sourced）

```python
# app/events/knowledge_events.py

from pydantic import BaseModel
from enum import Enum
from datetime import datetime

class KnowledgeStatus(str, Enum):
    NOT_OBSERVED = "未观察"
    INITIAL_CONTACT = "初步接触"
    NEEDS_CONSOLIDATION = "需要巩固"
    BASICALLY_MASTERED = "基本掌握"
    REPEATED_MISTAKES = "反复失误"

class KnowledgeUpdateEvent(BaseModel):
    event_id: str
    student_id: int
    knowledge_point_id: int
    previous_status: KnowledgeStatus
    new_status: KnowledgeStatus
    trigger_type: str  # quiz_correct, quiz_wrong, recall_success, recall_fail
    trigger_detail: dict
    timestamp: datetime

async def handle_knowledge_event(event: KnowledgeUpdateEvent, db: AsyncSession):
    """处理知识点状态变更事件"""
    # 1. 记录事件日志
    await save_event_log(event, db)
    
    # 2. 更新知识点状态
    await update_knowledge_status(
        student_id=event.student_id,
        knowledge_point_id=event.knowledge_point_id,
        new_status=event.new_status,
        db=db
    )
    
    # 3. 发布到消息队列供异步处理
    await publish_to_queue("knowledge_updates", event.model_dump())
```

#### 4.4.2 异步汇总（周维度 Cron Job）

```python
# app/tasks/weekly_aggregation.py

from celery import shared_task
from datetime import datetime, timedelta

class SubjectRiskLevel(str, Enum):
    STABLE = "稳定"
    LIGHT_RISK = "轻度风险"
    MEDIUM_RISK = "中度风险"
    HIGH_RISK = "高风险"

@shared_task
def aggregate_weekly_subject_risk():
    """
    每周日晚执行，汇总学科风险状态。

    注意：Celery worker 在同步上下文中运行。若底层 DB 操作使用
    SQLAlchemy 2.0 async，必须通过 asyncio.run() 桥接，否则会
    抛出 RuntimeError: no running event loop。
    不要直接 await 异步函数或使用 asyncio.get_event_loop()（在
    Python 3.10+ 中已弃用）。
    """
    import asyncio
    asyncio.run(_async_aggregate_weekly_subject_risk())


async def _async_aggregate_weekly_subject_risk():
    """异步实现，由 Celery task 通过 asyncio.run() 调用"""
    students = await get_all_active_students_async()

    for student in students:
        for subject in student.subjects:
            # 汇总本周数据 (注意显式声明时区，防止跨国服务器时区漂移)
            from zoneinfo import ZoneInfo
            weekly_stats = await calculate_weekly_stats_async(
                student_id=student.id,
                subject_id=subject.id,
                start_date=datetime.now(ZoneInfo("Asia/Shanghai")) - timedelta(days=7),
            )

            # 计算风险等级
            risk_level = calculate_risk_level(
                error_rate=weekly_stats.error_rate,
                recall_fail_rate=weekly_stats.recall_fail_rate,
                usage_frequency=weekly_stats.usage_frequency,
                score_trend=weekly_stats.score_trend,
            )

            # 更新学科风险状态
            await update_subject_risk_state_async(
                student_id=student.id,
                subject_id=subject.id,
                risk_level=risk_level,
                effective_week=get_current_week(),
            )
```

---

### 4.5 Assessment Agent 判断逻辑与输出格式

#### 4.5.1 状态迁移规则

Assessment Agent 在每次答疑会话结束后对本轮知识点交互做定性评估，输出状态变更建议。判断规则如下：

| 触发条件 | 当前状态 | 新状态 |
|---------|---------|-------|
| 本轮答疑一次答对（无提示） | 未观察 / 初步接触 | 基本掌握 |
| 本轮答疑经提示后答对 | 未观察 / 初步接触 | 需要巩固 |
| 本轮答疑答错或放弃 | 任意 | 初步接触（若首次）/ 需要巩固（若已接触）|
| 错题召回答对 | 需要巩固 / 基本掌握 | 基本掌握 |
| 错题召回再次答错（同一知识点累计 ≥ 2 次） | 任意 | 反复失误 |
| 人工纠偏 | 任意 | 人工指定状态 |

**连续掌握门槛**：升至"基本掌握"需满足同一知识点在不同会话中答对 ≥ 2 次（非同一会话连续答对）；仅凭单次会话答对，最高迁移至"需要巩固"。

#### 4.5.2 structured_summary 输出格式（JSON Schema）

Assessment Agent 将评估结果写入 `qa_sessions.structured_summary`，格式定义：

```json
{
  "session_id": 123,
  "assessed_at": "2026-03-18T21:30:00+08:00",
  "knowledge_point_updates": [
    {
      "knowledge_point_id": 42,
      "knowledge_point_name": "函数的定义域",
      "previous_status": "初步接触",
      "new_status": "需要巩固",
      "reason": "经提示后答对",
      "confidence": 0.85
    }
  ],
  "session_summary": {
    "total_questions": 3,
    "correct_first_try": 1,
    "correct_with_hint": 1,
    "incorrect": 1,
    "dominant_error_type": "概念不清"
  },
  "suggested_followup": "建议明日复习函数定义域与值域的区分"
}
```

`trigger_detail` 字段在 `knowledge_update_logs` 中存储对应 `knowledge_point_updates` 单条记录，以保证逐条可溯源。

---

### 4.6 OCR 异步处理完整流程

#### 4.6.1 上传到 OCR 完成的全流程

```
前端选择图片/文件
        │
        ▼
POST /student/material/upload
        │  返回: { upload_id, ocr_status: "pending" }
        ▼
后端: 写入 OSS → 创建 study_uploads 记录（ocr_status=pending）
        │
        ▼
发布 Celery 任务: process_ocr.delay(upload_id)
        │
        ▼ (异步，Celery Worker 执行)
┌──────────────────────────────────┐
│ 1. 从 OSS 下载原始文件           │
│ 2. 调用 Extraction Agent (VL)    │
│ 3. 解析 LaTeX + 题目结构化       │
│ 4. 更新 study_uploads:           │
│    ocr_result, extracted_questions│
│    ocr_status = "completed"      │
│    （失败时: ocr_status="failed" │
│     ocr_error=错误信息）          │
└──────────────────────────────────┘
        │
        ▼ (若 ocr_status=failed 且重试次数≤2)
自动重试 (Celery autoretry, max_retries=2, countdown=30s)
        │
        ▼ (超过重试次数)
创建 manual_corrections 待处理记录，触发人工纠偏
```

#### 4.6.2 前端轮询策略

```typescript
// 上传后轮询 OCR 状态
async function pollOcrStatus(uploadId: number): Promise<OcrResult> {
  const MAX_POLLS = 20;       // 最多轮询 20 次
  const POLL_INTERVAL = 3000; // 每 3 秒轮询一次（最长等待 60s）
  const TIMEOUT_MS = 60000;

  for (let i = 0; i < MAX_POLLS; i++) {
    const { data } = await api.get(`/student/material/${uploadId}/ocr-status`);
    if (data.ocr_status === "completed") return data.ocr_result;
    if (data.ocr_status === "failed") {
      // 展示"识别失败，请手动输入或联系管理员"提示
      throw new OcrFailedError(data.ocr_error);
    }
    await sleep(POLL_INTERVAL);
  }
  throw new OcrTimeoutError("OCR 超时，请稍后刷新");
}
```

#### 4.6.3 OCR 失败触发人工纠偏条件

| 条件 | 行为 |
|------|------|
| Celery 任务重试 3 次全部失败 | 写入 `manual_corrections`（target_type="ocr"），管理端出现待处理队列 |
| Extraction Agent 返回空结果 | 同上 |
| `ocr_status` 超过 5 分钟仍为 `processing` | Beat 定时检查，超时则标记 failed 并入队 |

---

### 4.7 冷启动设计（入学问卷）

#### 4.7.1 问题背景

新学生第一次使用时 `student_knowledge_status` 全为"未观察"，Planning Agent 无任何学情信号可用，无法生成有意义的推荐。冷启动通过入学问卷快速建立初始学情。

#### 4.7.2 入学问卷字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `grade` | SELECT | 高一 / 高二 / 高三 |
| `textbook_version` | SELECT | 各科教材版本（数学A/B版等）|
| `subject_combination` | MULTISELECT | 已选科目（物化生/史地政等）|
| `weak_subjects` | MULTISELECT | 自评薄弱学科（最多 3 门）|
| `recent_exam_scores` | JSONB | 最近一次月考各科成绩（可跳过）|
| `error_types_by_subject` | JSONB | 各科常见错误类型自评（计算/概念/粗心）|
| `daily_study_minutes` | NUMBER | 日均课后学习时间（分钟）|
| `upcoming_exam_date` | DATE | 近期最重要考试日期（可选）|

#### 4.7.3 问卷结果 → 初始状态映射规则

```python
# app/onboarding/state_initializer.py

def initialize_student_states(onboarding_data: dict, student_id: int) -> list[KnowledgeStatusSeed]:
    """
    将入学问卷映射为初始知识点状态和学科风险状态。
    """
    seeds = []

    # 规则1: 自评薄弱学科 → 该学科章级知识点初始化为"初步接触"
    for subject_code in onboarding_data.get("weak_subjects", []):
        chapter_ids = get_chapter_level_points(subject_code)
        for kp_id in chapter_ids:
            seeds.append(KnowledgeStatusSeed(
                knowledge_point_id=kp_id,
                status="初步接触",
                reason="onboarding_weak_subject"
            ))

    # 规则2: 月考成绩 < 60% 满分 → 对应学科风险标记为"中度风险"
    for subject_code, score in onboarding_data.get("recent_exam_scores", {}).items():
        full_score = 150 if subject_code in ("chinese", "math", "english") else 100
        if score / full_score < 0.6:
            mark_subject_risk(student_id, subject_code, "中度风险", reason="onboarding_low_score")
        elif score / full_score < 0.75:
            mark_subject_risk(student_id, subject_code, "轻度风险", reason="onboarding_score")

    # 规则3: 无月考成绩 + 自评薄弱 → 轻度风险兜底
    for subject_code in onboarding_data.get("weak_subjects", []):
        if subject_code not in onboarding_data.get("recent_exam_scores", {}):
            mark_subject_risk(student_id, subject_code, "轻度风险", reason="onboarding_self_report")

    return seeds
```

完成问卷后：
1. 调用 `initialize_student_states()` 写入初始知识点状态批次
2. 将 `student_profiles.onboarding_completed` 更新为 `true`
3. Planning Agent 在 `onboarding_completed=false` 时拒绝生成个性化计划并引导完成问卷

---

### 4.8 knowledge_tree 数据初始化方案

#### 4.8.1 数据来源

知识树初始数据基于"上海高考考纲 + 历年真题标注"生成，分两步：

1. **人工录入骨架**：参照上海市高考考试说明，手动录入三层结构（章/节/知识点），覆盖 MVP 5 门科目（语文/数学/英语/物理/化学）
2. **GPT-4o 标注 importance_score**：将历年真题（近 5 年，2020–2024 年上海高考真题）与知识树知识点进行匹配，统计 `exam_frequency`，再结合考纲级别计算 `importance_score`

#### 4.8.2 importance_score 计算公式

```
importance_score = 归一化(exam_frequency) × 0.4
                 + 归一化(score_weight)     × 0.4
                 + syllabus_weight           × 0.2

syllabus_weight: 了解=0.3, 理解=0.6, 掌握=1.0
score_weight: 该知识点对应题型的平均分值（如大题=12分, 小题=4分）
归一化: 按同学科内最大值做 min-max 归一化
```

#### 4.8.3 Seed Data 脚本规范

```python
# scripts/seed_knowledge_tree.py
# 运行: python scripts/seed_knowledge_tree.py --subject math --dry-run

"""
Seed 脚本说明：
- 从 data/syllabus/<subject>.json 读取人工整理的知识树结构
- 从 data/exam_questions/<subject>_2020_2024.json 读取历年真题标注
- 计算每个知识点的 exam_frequency、importance_score
- 写入 knowledge_tree 表（使用 upsert on conflict code DO UPDATE）
- --dry-run 参数：只输出待写入数据，不实际写入
"""
```

数据文件路径约定：
- `data/syllabus/math.json` — 数学知识树骨架（人工整理）
- `data/exam_questions/math_2020_2024.json` — 历年真题与知识点映射（GPT-4o 标注后人工审核）

---

## 5. API 分层设计

### 5.0 全局限流策略 (Rate Limiting)
基于 Redis + fastapi-limiter 限制异常刷量与控制大模型成本，核心接口策略配置：
*   `/api/v1/student/qa/chat/stream`: 同一学生并发限 1 个请求，每分钟最多 5 次。
*   `/api/v1/student/material/upload`: 同一学生每分钟最多 10 次。
*   `/api/v1/student/plan/generate`: 同一学生每小时最多 3 次。

### 5.1 学生端 API

```
POST   /api/v1/student/profile                   # 创建学生档案（首次建档）
GET    /api/v1/student/profile                   # 获取学生档案
PATCH  /api/v1/student/profile                   # 更新学生信息

POST   /api/v1/student/onboarding/submit         # 提交入学问卷（冷启动，首次必填）
GET    /api/v1/student/onboarding/status         # 查询入学问卷完成状态

POST   /api/v1/student/plan/generate             # 生成今日计划
GET    /api/v1/student/plan/today                # 获取今日计划
PATCH  /api/v1/student/plan/mode                 # 切换学习模式
PATCH  /api/v1/student/plan/tasks/{taskId}       # 更新任务状态

POST   /api/v1/student/material/upload           # 上传学习材料
GET    /api/v1/student/material/list             # 获取上传历史
GET    /api/v1/student/material/{id}/ocr-status  # 查询 OCR 状态
POST   /api/v1/student/material/{id}/retry-ocr   # 重试 OCR

POST   /api/v1/student/qa/chat                   # 发送答疑消息
POST   /api/v1/student/qa/chat/stream            # 流式答疑
GET    /api/v1/student/qa/history                # 获取答疑历史
GET    /api/v1/student/qa/sessions/{sessionId}   # 获取答疑会话详情

GET    /api/v1/student/errors                    # 获取错题列表
GET    /api/v1/student/errors/{id}               # 获取错题详情
GET    /api/v1/student/errors/summary            # 获取错题摘要
POST   /api/v1/student/errors/{id}/recall        # 触发错题再次召回
POST   /api/v1/student/errors/batch-recall       # 批量错题召回

GET    /api/v1/student/knowledge/status          # 获取知识点掌握状态
GET    /api/v1/student/report/weekly             # 获取周报（学生视角）
GET    /api/v1/student/report/weekly/summary     # 获取周报概览

GET    /api/v1/config/textbook-versions          # 获取教材版本列表
```

### 5.2 家长端 API

```
GET    /api/v1/parent/report/weekly           # 获取周报（家长视角）
GET    /api/v1/parent/report/stage            # 获取阶段报告
POST   /api/v1/parent/report/share            # 生成分享链接
GET    /api/v1/parent/profile/risk            # 获取学科风险概览
GET    /api/v1/parent/profile/trend           # 获取趋势数据

POST   /api/v1/parent/profile/supplement      # 补录基础信息
POST   /api/v1/parent/exam/record             # 补录考试成绩
```

### 5.3 分享链接 API

```
GET    /api/v1/share/{token}                  # 获取分享内容
GET    /api/v1/share/{token}/validate         # 验证链接有效性
```

分享链接采用带过期时间的 JWT 签名，内部硬编码 Omit 规则：

```python
SHARE_OMIT_FIELDS = [
    "original_images",      # 原始图片
    "full_qa_history",      # 完整答疑记录
    "rank_details",         # 详细排名
    "error_book_full",      # 完整错题本
    "admin_notes",          # 人工标注
]
```

### 5.4 管理端 API

```
# 模式管理
GET    /api/v1/admin/system/mode              # 获取当前运行模式
POST   /api/v1/admin/system/mode              # 切换运行模式

# 人工纠偏
GET    /api/v1/admin/corrections/pending      # 待处理纠偏列表
GET    /api/v1/admin/corrections/{id}         # 获取纠偏项详情
GET    /api/v1/admin/corrections/logs         # 获取修正记录
POST   /api/v1/admin/corrections/ocr          # 修正 OCR 结果
POST   /api/v1/admin/corrections/knowledge    # 修正知识点标注
POST   /api/v1/admin/corrections/plan         # 调整计划

# 监控
GET    /api/v1/admin/metrics/today            # 今日概览数据
GET    /api/v1/admin/metrics/health           # 系统健康状态
GET    /api/v1/admin/metrics/model-calls      # 模型调用统计
GET    /api/v1/admin/metrics/costs            # 成本统计
GET    /api/v1/admin/metrics/errors           # 错误统计
GET    /api/v1/admin/metrics/fallbacks        # 降级统计
GET    /api/v1/admin/metrics/latency          # 延迟统计
```

### 5.5 认证 API

```
POST   /api/v1/auth/token-login               # Token 登录（学生/家长）
POST   /api/v1/auth/admin-login               # 管理员账号密码登录
```

---

## 6. 数据库设计

### 6.1 核心实体模型

#### 6.1.1 用户与学生档案

```sql
-- 用户表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE,
    nickname VARCHAR(100),
    avatar_url VARCHAR(500),
    role VARCHAR(20) NOT NULL DEFAULT 'student',  -- student, parent, admin
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 学生档案表
CREATE TABLE student_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    grade VARCHAR(20) NOT NULL,                    -- 高一/高二/高三
    textbook_version VARCHAR(50),                  -- 教材版本
    class_rank INTEGER,                            -- 班级排名
    grade_rank INTEGER,                            -- 年级排名
    subject_combination JSONB NOT NULL DEFAULT '[]', -- 选科组合
    upcoming_exams JSONB DEFAULT '[]',             -- 近期考试节点
    current_progress JSONB DEFAULT '{}',           -- 当前学习进度
    onboarding_completed BOOLEAN NOT NULL DEFAULT false, -- 入学问卷是否已完成（冷启动标志）
    onboarding_data JSONB DEFAULT '{}',            -- 入学问卷原始填写数据
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)
);

-- 考试记录表
CREATE TABLE exam_records (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student_profiles(id),
    exam_type VARCHAR(50) NOT NULL,                -- 月考/期中/期末/周测
    exam_date DATE NOT NULL,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    score DECIMAL(5,2),
    full_score DECIMAL(5,2) DEFAULT 100,
    class_rank INTEGER,
    grade_rank INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(20) DEFAULT 'student'       -- student/parent/admin
);

CREATE INDEX idx_exam_records_student ON exam_records(student_id, exam_date DESC);
```

#### 6.1.2 学科与知识树

```sql
-- 学科表
CREATE TABLE subjects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,              -- 数学/语文/英语...
    code VARCHAR(20) NOT NULL UNIQUE,              -- math/chinese/english...
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- 知识树表
CREATE TABLE knowledge_tree (
    id SERIAL PRIMARY KEY,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    parent_id INTEGER REFERENCES knowledge_tree(id),
    name VARCHAR(200) NOT NULL,                    -- 知识点名称
    code VARCHAR(100),                             -- 知识点编码
    level INTEGER NOT NULL DEFAULT 1,              -- 层级 1-章 2-节 3-点
    description TEXT,
    textbook_versions JSONB DEFAULT '[]',          -- 适用教材版本
    importance_score DECIMAL(5,4) DEFAULT 0.5,     -- 归一化重要性分 0.0-1.0，由考纲+频次计算
    exam_frequency INTEGER DEFAULT 0,              -- 近年（近5年）上海高考出现次数
    last_exam_year INTEGER,                        -- 最近出现的年份
    syllabus_level VARCHAR(20),                    -- 考纲要求级别: 了解/理解/掌握
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_tree_subject ON knowledge_tree(subject_id);
CREATE INDEX idx_knowledge_tree_parent ON knowledge_tree(parent_id);

-- 学生知识点状态表
CREATE TABLE student_knowledge_status (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student_profiles(id),
    knowledge_point_id INTEGER NOT NULL REFERENCES knowledge_tree(id),
    status VARCHAR(30) NOT NULL DEFAULT '未观察',   -- 未观察/初步接触/需要巩固/基本掌握/反复失误
    last_update_reason VARCHAR(100),               -- 最近更新原因
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_manual_corrected BOOLEAN DEFAULT false,     -- 是否人工修正
    UNIQUE(student_id, knowledge_point_id)
);

CREATE INDEX idx_student_knowledge_student ON student_knowledge_status(student_id);
CREATE INDEX idx_student_knowledge_status ON student_knowledge_status(status);
```

#### 6.1.3 学习计划与任务

```sql
-- 每日计划表
CREATE TABLE daily_plans (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student_profiles(id),
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    plan_date DATE NOT NULL,
    learning_mode VARCHAR(30) NOT NULL,            -- workday_follow/weekend_review
    system_recommended_mode VARCHAR(30),           -- 系统推荐模式
    available_minutes INTEGER NOT NULL,
    source VARCHAR(30) NOT NULL,                   -- upload_corrected/history_inferred/manual_adjusted/generic_fallback
    is_history_inferred BOOLEAN DEFAULT false,
    recommended_subjects JSONB NOT NULL,           -- [{subject_id, reasons: [...]}]
    plan_content JSONB NOT NULL,                   -- 完整计划 JSON
    status VARCHAR(20) NOT NULL DEFAULT 'generated', -- generated/in_progress/completed
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(student_id, plan_date)
);

CREATE INDEX idx_daily_plans_student_date ON daily_plans(student_id, plan_date DESC);

-- 计划任务表
CREATE TABLE plan_tasks (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES daily_plans(id),
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    task_type VARCHAR(50) NOT NULL,                -- lecture/practice/error_review/consolidation
    task_content JSONB NOT NULL,                   -- 任务详情
    sequence INTEGER NOT NULL,                     -- 任务顺序
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending/entered/executed/completed
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_minutes INTEGER
);

CREATE INDEX idx_plan_tasks_plan ON plan_tasks(plan_id);
```

#### 6.1.4 上传与错题

```sql
-- 学习材料上传表
CREATE TABLE study_uploads (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student_profiles(id),
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    upload_type VARCHAR(30) NOT NULL,              -- note/homework/test/handout/score
    file_hash VARCHAR(64) NOT NULL,                -- 文件的 SHA256/MD5，用于上传秒传与防重复 OCR
    original_url VARCHAR(500) NOT NULL,            -- OSS 原始文件 URL
    thumbnail_url VARCHAR(500),                    -- 缩略图 URL
    ocr_result JSONB,                              -- OCR 结构化结果
    extracted_questions JSONB DEFAULT '[]',        -- 提取的题目列表
    subject_id INTEGER REFERENCES subjects(id),
    knowledge_points JSONB DEFAULT '[]',           -- 关联知识点 ID 列表
    ocr_status VARCHAR(20) DEFAULT 'pending',      -- pending/processing/completed/failed
    ocr_error TEXT,
    is_manual_corrected BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_study_uploads_student ON study_uploads(student_id, created_at DESC);
CREATE INDEX idx_study_uploads_ocr_status ON study_uploads(ocr_status);

-- 错题本表
CREATE TABLE error_book (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student_profiles(id),
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    question_content JSONB NOT NULL,               -- 题目内容（含 LaTeX）
    question_image_url VARCHAR(500),               -- 原题图片
    knowledge_points JSONB NOT NULL DEFAULT '[]',  -- 关联知识点
    error_type VARCHAR(50),                        -- 计算错误/概念不清/粗心/不会
    entry_reason VARCHAR(50) NOT NULL,             -- wrong/not_know/repeated_wrong
    content_hash VARCHAR(64),                      -- SHA256(question_text + sorted knowledge_point_ids)，应用层去重键
    is_explained BOOLEAN DEFAULT false,            -- 是否已讲解
    is_recalled BOOLEAN DEFAULT false,             -- 是否已召回
    last_recall_at TIMESTAMPTZ,
    last_recall_result VARCHAR(20),                -- success/fail
    recall_count INTEGER DEFAULT 0,
    source_upload_id INTEGER REFERENCES study_uploads(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_error_book_student ON error_book(student_id);
CREATE INDEX idx_error_book_subject ON error_book(subject_id);
CREATE INDEX idx_error_book_recall ON error_book(is_recalled, last_recall_at);
CREATE UNIQUE INDEX idx_error_book_dedup ON error_book(student_id, content_hash) WHERE content_hash IS NOT NULL;
```

#### 6.1.5 答疑记录

```sql
-- 答疑会话表
CREATE TABLE qa_sessions (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student_profiles(id),
    session_date DATE NOT NULL,
    task_id INTEGER REFERENCES plan_tasks(id),
    subject_id INTEGER REFERENCES subjects(id),
    status VARCHAR(20) DEFAULT 'active',           -- active/closed
    structured_summary JSONB,                      -- Assessment Agent 输出的结构化评估（见 §4.5 格式定义）
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

CREATE INDEX idx_qa_sessions_student ON qa_sessions(student_id, created_at DESC);

-- 答疑消息表
CREATE TABLE qa_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES qa_sessions(id),
    role VARCHAR(20) NOT NULL,                     -- user/assistant
    content TEXT NOT NULL,
    attachments JSONB DEFAULT '[]',                -- 附件（图片等）
    intent VARCHAR(50),                            -- upload_question/ask/follow_up/chat
    related_question_id INTEGER REFERENCES error_book(id),
    knowledge_points JSONB DEFAULT '[]',
    tutoring_strategy VARCHAR(50),                 -- hint/step_by_step/formula/full_solution
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_qa_messages_session ON qa_messages(session_id);

-- 知识点状态变更日志
CREATE TABLE knowledge_update_logs (
    id BIGSERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student_profiles(id),
    knowledge_point_id INTEGER NOT NULL REFERENCES knowledge_tree(id),
    previous_status VARCHAR(30),
    new_status VARCHAR(30) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,             -- quiz_correct/quiz_wrong/recall_success/recall_fail/manual
    trigger_detail JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_logs_student ON knowledge_update_logs(student_id, created_at DESC);
```

#### 6.1.6 学科风险与报告

```sql
-- 学科风险状态表
CREATE TABLE subject_risk_states (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student_profiles(id),
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    risk_level VARCHAR(20) NOT NULL DEFAULT '稳定', -- 稳定/轻度风险/中度风险/高风险
    effective_week VARCHAR(10) NOT NULL,           -- 2026-W12 格式
    calculation_detail JSONB,                      -- 计算明细
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(student_id, subject_id, effective_week)
);

CREATE INDEX idx_risk_states_student ON subject_risk_states(student_id);

-- 周报表
CREATE TABLE weekly_reports (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student_profiles(id),
    report_week VARCHAR(10) NOT NULL,              -- 2026-W12 格式
    usage_days INTEGER,
    total_minutes INTEGER,
    student_view_content JSONB NOT NULL,           -- 学生视角内容
    parent_view_content JSONB NOT NULL,            -- 家长视角内容
    share_summary JSONB NOT NULL,                  -- 分享摘要
    share_token VARCHAR(100) UNIQUE,
    share_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(student_id, report_week)
);

CREATE INDEX idx_weekly_reports_student ON weekly_reports(student_id, report_week DESC);
```

#### 6.1.7 模型调用日志

```sql
-- 模型调用日志表
CREATE TABLE model_call_logs (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL,
    student_id INTEGER REFERENCES student_profiles(id),
    agent_name VARCHAR(50) NOT NULL,
    mode VARCHAR(10) NOT NULL,                     -- normal/best
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    latency_ms INTEGER NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    is_fallback BOOLEAN DEFAULT false,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    estimated_cost DECIMAL(10,6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_model_logs_created ON model_call_logs(created_at DESC);
CREATE INDEX idx_model_logs_agent ON model_call_logs(agent_name, created_at DESC);

-- 人工纠偏记录表
CREATE TABLE manual_corrections (
    id SERIAL PRIMARY KEY,
    target_type VARCHAR(50) NOT NULL,              -- ocr/knowledge/plan/qa
    target_id INTEGER NOT NULL,
    original_content JSONB,
    corrected_content JSONB NOT NULL,
    correction_reason TEXT,
    corrected_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_corrections_type ON manual_corrections(target_type, created_at DESC);
```

### 6.2 知识树设计

知识树采用三层结构：章 → 节 → 知识点

> **数据初始化说明**：完整的知识树 seed data 通过 `scripts/seed_knowledge_tree.py` 生成写入，
> 详见 §4.8。下方仅为结构示例，不代表完整数据。

```sql
-- 示例：数学知识树初始化（含 importance_score 字段）
INSERT INTO knowledge_tree (subject_id, parent_id, name, code, level, syllabus_level, exam_frequency, importance_score) VALUES
-- 高一数学
(1, NULL, '集合与常用逻辑用语', 'math-set', 1, '理解', 3, 0.55),
(1, 1, '集合的概念与表示', 'math-set-concept', 2, '理解', 2, 0.50),
(1, 2, '集合的含义', 'math-set-concept-meaning', 3, '了解', 1, 0.35),
(1, 2, '集合的表示方法', 'math-set-concept-notation', 3, '理解', 2, 0.50),
(1, 1, '集合间的基本关系', 'math-set-relation', 2, '掌握', 4, 0.75),
(1, 5, '子集与真子集', 'math-set-relation-subset', 3, '掌握', 3, 0.68),

(1, NULL, '函数', 'math-function', 1, '掌握', 8, 0.92),
(1, 7, '函数的概念', 'math-function-concept', 2, '掌握', 6, 0.85),
(1, 8, '函数的定义域', 'math-function-concept-domain', 3, '掌握', 5, 0.80),
(1, 8, '函数的值域', 'math-function-concept-range', 3, '掌握', 4, 0.72);
```

---

## 7. 部署架构

### 7.1 首期部署方案（Docker Compose）

```yaml
# docker-compose.yml
version: '3.8'

services:
  # API 服务
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/studypilot
      - REDIS_URL=redis://redis:6379/0
      - TZ=Asia/Shanghai
      - DASHSCOPE_API_KEY=${DASHSCOPE_API_KEY}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OSS_ACCESS_KEY=${OSS_ACCESS_KEY}
      - OSS_SECRET_KEY=${OSS_SECRET_KEY}
      - OSS_BUCKET=${OSS_BUCKET}
      - OSS_ENDPOINT=${OSS_ENDPOINT}
    volumes:
      - ./config:/app/config
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # Celery Worker
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.tasks worker -l info
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/studypilot
      - REDIS_URL=redis://redis:6379/0
      - TZ=Asia/Shanghai
    volumes:
      - ./config:/app/config
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # Celery Beat (定时任务)
  beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.tasks beat -l info
    environment:
      - REDIS_URL=redis://redis:6379/0
      - TZ=Asia/Shanghai
    depends_on:
      - redis
    restart: unless-stopped

  # 前端服务
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
    depends_on:
      - api
    restart: unless-stopped

  # PostgreSQL
  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=studypilot
    restart: unless-stopped

  # Redis
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  # Nginx 反向代理
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - api
      - frontend
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### 7.2 关键中间件

| 中间件 | 用途 | 配置要点 |
|--------|------|---------|
| **Nginx** | 反向代理、SSL 终止、静态资源 | 配置 WebSocket 支持用于流式响应 |
| **Redis** | 缓存、会话、Celery Broker | 配置持久化避免数据丢失 |
| **PostgreSQL** | 主数据存储 | 配置定期备份 |

### 7.3 监控与告警

#### 7.3.1 监控指标

| 指标类别 | 指标名称 | 告警阈值 |
|---------|---------|---------|
| **API** | 请求延迟 P99 | > 3s |
| **API** | 错误率 | > 5% |
| **LLM** | 调用延迟 P95 | > 30s |
| **LLM** | 降级率 | > 20% |
| **LLM** | 日成本 | > 预算 120% |
| **数据库** | 连接数 | > 80% |
| **Redis** | 内存使用 | > 80% |

#### 7.3.2 日志收集

```python
# app/core/logging.py

import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# 使用示例
logger = structlog.get_logger()
logger.info("plan_generated", student_id=123, mode="workday_follow", subjects=["math", "physics"])
```

---

## 8. 安全设计

> **定位说明**：本系统为小范围自用（家中孩子及少量熟人学生），不对外运营、不接入学校系统、不涉及商业化。安全设计以实用为主，确保基本数据安全，不追求商业级合规标准。

### 8.1 设计原则

1. **实用优先**：满足自用场景的基本安全需求，不过度设计
2. **数据保护**：防止数据意外泄露到公网，保障基本隐私
3. **简单可维护**：认证方案简单实用，便于运营者管理

### 8.2 基础安全措施

| 措施 | 说明 |
|------|------|
| **HTTPS 传输** | 所有 API 请求通过 HTTPS 加密传输 |
| **数据库访问控制** | PostgreSQL 密码保护，仅允许内网访问 |
| **API 基本鉴权** | 防止接口裸露在公网，未授权访问返回 401 |
| **定期数据备份** | 每日自动备份数据库，保留 7 天 |
| **分享链接过期** | 分享链接带过期时间，默认 7 天有效 |

### 8.3 数据存储

| 项目 | 方案 |
|------|------|
| **数据存储** | 阿里云华东区，境内存储 |
| **模型选择** | 正常效果模式默认使用国产模型（Qwen/DeepSeek）|
| **文件存储** | 阿里云 OSS 私有读写，上传内容仅自用学习材料 |

### 8.4 敏感数据处理

自用场景下不做字段级加密，保留基本脱敏处理：

```python
# app/core/data_masking.py

SENSITIVE_FIELDS = {
    "class_rank",
    "grade_rank", 
    "original_images",
    "full_qa_history",
    "exam_scores_detail",
}

def mask_for_share(data: dict) -> dict:
    """分享链接数据脱敏"""
    return {k: v for k, v in data.items() if k not in SENSITIVE_FIELDS}
```

### 8.5 简化认证方案

首期采用简单实用的认证方案，区分学生/家长/管理员访问即可：

| 角色 | 认证方式 | 权限范围 |
|------|---------|----------|
| **学生** | 简单 Token（首次登录生成）| 本人数据读写 |
| **家长** | 简单 Token + 学生绑定 | 关联学生的报告查看 |
| **管理员** | 账号密码 | 纠偏、模式切换、监控（运营者本人）|
| **分享链接** | 带过期的签名 URL | 仅摘要数据只读 |

```python
# app/core/auth.py

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_student(
    token: str = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> StudentProfile:
    """验证学生 Token"""
    payload = verify_token(token.credentials)
    if payload.get("role") != "student":
        raise HTTPException(403, "Student access required")
    return await get_student_by_id(payload["user_id"], db)

async def require_admin(
    token: str = Depends(security)
) -> User:
    """验证管理员（运营者本人）"""
    payload = verify_token(token.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return await get_user_by_id(payload["user_id"])
```

### 8.6 不涉及的安全要求

以下为商业产品常见的安全合规要求，本自用系统首期不涉及：

1. ~~《个人信息保护法》正式合规审计~~
2. ~~GDPR 等海外数据合规~~
3. ~~数据合规认证~~
4. ~~OSS 内容安全审核/鉴黄~~（上传内容为自家学习材料）
5. ~~字段级数据加密~~
6. ~~复杂的多因素认证~~
7. ~~独立的安全审计日志系统~~

---

## 附录：关键设计决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| Agent 编排框架 | LangGraph | 支持状态机、易于调试、与 LangChain 生态兼容 |
| 双模式设计 | 手动切换 | 首期用户少，运维可根据反馈灵活调整 |
| 学习模式 | 工作日跟学 + 周末复习 | MVP 收敛，考试冲刺延后 |
| 状态更新策略 | 知识点实时 + 学科风险周汇总 | 平衡即时反馈与状态稳定性 |
| 错题召回 | P0 必做 | PRD 明确要求，验证学习闭环 |
| ModelRouter 模式存储 | Redis（key: system:run_mode） | YAML 文件写后其他进程内存不同步；Redis 多进程共享一致 |
| Celery async DB 操作 | asyncio.run() 桥接 | Celery worker 同步上下文；直接 await 抛出 RuntimeError |
| Assessment 触发时机 | Tutoring 流式结束后 Redis queue 异步触发 | 不阻塞用户看到响应，同时保证评估完整性 |
| 冷启动方案 | 入学问卷 → 初始知识点状态批量写入 | Day 1 无历史数据，问卷提供最小可用学情信号 |
| 错题去重 | content_hash（SHA256）+ 唯一索引 | 避免同一道题多次上传重复入库 |
| knowledge_tree importance_score | 频次×0.4 + 分值权重×0.4 + 考纲级别×0.2 | 加权覆盖"考得多""分值高""考纲要求高"三个维度 |
