# Phase 5 详细设计：辅助功能完善与增强

> **状态**：待实施
> **创建日期**：2026-03-20

## 1. 目标与范围

在 Phase 1-4 已完成的基础上（后端基础设施 + P0 API + LLM Agent + 前后端联调），对辅助模块进行功能完善和增强，使其达到 MVP 生产可用状态。

**范围边界**：
- 本阶段聚焦于周报增强、分享链接优化、管理后台深化、纠偏流程完善
- 不包含考试冲刺模式（P1，后续版本）
- 不包含 Phase 6 的测试与部署工作

**交付物**：
1. 周报页面增加周期选择器、上周对比、学科趋势图
2. 家长周报增加风险摘要、成绩变化、家长支持建议
3. 管理后台增加成本追踪、降级统计、错误统计、延迟指标
4. 纠偏页面增加详情面板（OCR 图片预览、知识点选择器）
5. 纠偏流程增加计划纠偏类型和修正历史记录
6. 新增管理端 API：成本趋势、降级统计、错误统计、延迟分位数、纠偏详情、修正记录

---

## 2. 现状分析

### 2.1 已实现的基础能力

| 模块 | 后端 | 前端 | 完成度 |
|------|------|------|--------|
| 周报生成（Celery Beat 定时任务） | ✅ `tasks/weekly_report.py` | — | 100% |
| 周报数据构建（usage_days, completion_rate, subject_trends, risk_points） | ✅ `services/report.py` | — | 100% |
| 学生周报页面 | ✅ 3 端点 | ✅ 基础展示 | 85% |
| 家长周报页面 | ✅ 5 端点 | ✅ 基础展示 | 70% |
| 分享链接 | ✅ JWT 签名 + 脱敏 | ✅ 公开页面 | 90% |
| 管理仪表盘 | ✅ 今日概览 + 健康检查 + 模型调用 | ✅ 基础展示 | 60% |
| 纠偏处理 | ✅ OCR/Knowledge 修正 + resolve | ✅ 列表 + 标记处理 | 65% |
| 监控统计 | ✅ 基础聚合 | ✅ 基础展示 | 40% |

### 2.2 待完善的功能缺口

**高优先级（MVP 必需）**：

1. **周期选择器缺失** — 学生和家长周报页面只能查看最新一期，无法浏览历史周报
2. **上周对比数据缺失** — 核心指标（学习天数、时长、完成率）无趋势变化展示
3. **管理端指标不足** — 缺少成本趋势、降级率、错误率、延迟分位数等生产运维必需指标
4. **纠偏详情面板缺失** — 纠偏页面只有列表视图，无法查看原始图片、题目内容等上下文
5. **修正历史记录缺失** — 无法查看已处理纠偏的历史记录

**中优先级（MVP 增强）**：

6. **家长周报内容不完整** — 缺少风险摘要区、成绩变化表格、家长支持建议区
7. **计划纠偏类型缺失** — 后端只支持 OCR 和 Knowledge 纠偏，缺少 Plan 类型
8. **纠偏分类统计缺失** — 仪表盘待处理事项缺少按类型计数

---

## 3. 新增与修改文件清单

### 3.1 后端新增文件

```
server/app/
├── schemas/
│   └── metrics.py              # 新增：成本/降级/错误/延迟响应 schema
└── (无新增 service/endpoint 文件，在已有文件中扩展)
```

### 3.2 后端修改文件

| 文件 | 变更内容 |
|------|---------|
| `app/schemas/admin.py` | 新增 CostTrendOut, FallbackStatsOut, ErrorStatsOut, LatencyStatsOut, CorrectionDetailOut, CorrectionLogOut, PlanCorrectionRequest, PendingCountByTypeOut |
| `app/services/admin.py` | 新增 7 个函数：get_cost_trend, get_fallback_stats, get_error_stats, get_latency_stats, get_correction_detail, get_correction_logs, correct_plan, get_pending_count_by_type |
| `app/services/report.py` | 新增 get_previous_week_report() 用于上周对比；增强 build_weekly_report_payload() 输出 parent_support_suggestions |
| `app/api/v1/endpoints/admin.py` | 新增 7 个端点 |
| `app/api/v1/endpoints/report.py` | 新增 week 列表端点返回格式增强 |

### 3.3 前端新增文件

```
web/src/
├── components/
│   ├── report/
│   │   └── week-selector.tsx           # 周期选择器组件
│   └── admin/
│       ├── ocr-correction-panel.tsx     # OCR 纠偏详情面板
│       ├── knowledge-correction-panel.tsx  # 知识点纠偏面板
│       └── correction-log-list.tsx      # 修正历史记录
```

### 3.4 前端修改文件

| 文件 | 变更内容 |
|------|---------|
| `src/lib/hooks.ts` | 新增 7 个 hooks：useWeeklyReportByWeek, useParentReportByWeek, useCostTrend, useFallbackStats, useErrorStats, useLatencyStats, useCorrectionLogs |
| `src/types/api.ts` | 新增 CostTrendData, FallbackStatsData, ErrorStatsData, LatencyStatsData, CorrectionLogItem 类型 |
| `src/app/report/weekly/page.tsx` | 集成 WeekSelector，增加上周对比指标 |
| `src/app/parent/report/weekly/page.tsx` | 集成 WeekSelector，增加风险摘要区、成绩变化区、家长支持建议区 |
| `src/app/admin/dashboard/page.tsx` | 增加模型调用摘要卡片（成本/降级率）、按类型分类的待处理计数 |
| `src/app/admin/corrections/page.tsx` | 增加详情面板（列表+详情双栏布局）、修正历史记录区 |
| `src/app/admin/metrics/page.tsx` | 增加成本趋势图、降级统计、错误统计、延迟分位数展示 |

---

## 4. 新增 API 端点

### 4.1 管理端指标扩展

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/admin/metrics/costs` | admin | 成本趋势（按天/小时） |
| GET | `/admin/metrics/fallbacks` | admin | 降级统计（次数/率/原因分布） |
| GET | `/admin/metrics/errors` | admin | 错误统计（总数/按类型） |
| GET | `/admin/metrics/latency` | admin | 延迟分位数（avg/P95/P99） |

### 4.2 纠偏扩展

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/admin/corrections/{id}` | admin | 纠偏项详情（含原始内容上下文） |
| GET | `/admin/corrections/logs` | admin | 修正历史记录（分页） |
| POST | `/admin/corrections/plan` | admin | 提交计划纠偏 |
| GET | `/admin/corrections/pending/count` | admin | 按类型统计待处理数量 |

---

## 5. 详细设计

### 5.1 周报增强

#### 5.1.1 周期选择器

**组件**：`WeekSelector`

```
┌──────────────────────────────────────────────┐
│  ◀ 返回       本周学习报告   [▼ 第12周 3.11-3.17] │
└──────────────────────────────────────────────┘
```

**交互规格**：
- 点击展开下拉，显示最近 8 周列表
- 每项格式：`第{N}周 {M.D}-{M.D}`
- 默认选中当前周（若当前周报未生成，自动回退到上一周）
- 选择后调用 `GET /student/report/weekly?week={YYYY-WNN}` 刷新数据

**数据计算**：前端根据当前日期计算最近 8 周的 ISO 周号和日期范围，无需后端支持。

**SWR Hook 变更**：

```typescript
// 修改 useWeeklyReport 支持 week 参数
export function useWeeklyReport(week?: string) {
  const path = week
    ? `/student/report/weekly?week=${week}`
    : "/student/report/weekly";
  return useSWR<WeeklyReport>(path, fetcher);
}

export function useParentWeeklyReport(week?: string) {
  const path = week
    ? `/parent/report/weekly?week=${week}`
    : "/parent/report/weekly";
  return useSWR<ParentWeeklyReport>(path, fetcher);
}
```

#### 5.1.2 上周对比数据

**后端变更**：`services/report.py` 新增函数

```python
async def get_previous_week_report(
    db: AsyncSession, student_id: int, current_week: str
) -> WeeklyReport | None:
    """获取上一周的周报，用于对比指标"""
    year_str, week_str = current_week.split("-W")
    year, week = int(year_str), int(week_str)
    if week == 1:
        prev_week = f"{year - 1}-W52"
    else:
        prev_week = f"{year}-W{week - 1:02d}"

    result = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.student_id == student_id,
            WeeklyReport.report_week == prev_week,
        )
    )
    return result.scalar_one_or_none()
```

**端点变更**：`GET /student/report/weekly` 响应增加 `previous` 字段

```python
class WeeklyReportWithComparison(BaseModel):
    # ... 现有字段
    previous_usage_days: int | None = None
    previous_total_minutes: int | None = None
    previous_task_completion_rate: float | None = None
```

**前端展示**：

```
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   📅 学习天数    │ │   ⏱️ 总时长     │ │   ✅ 完成率     │
│                 │ │                 │ │                 │
│    5 / 7 天     │ │    4h 32min     │ │     78%        │
│   ↑ 比上周+1    │ │  ↑ 比上周+45min │ │   ↓ 比上周-5%   │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

对比逻辑：
- 正增长：绿色 `↑`
- 负增长：红色 `↓`
- 无变化：灰色 `→`
- 无上周数据：不显示对比行

#### 5.1.3 家长周报增强

**当前缺失 vs PRD 要求对照**：

| PRD 要求（page-prd-auxiliary.md P2） | 当前状态 | 本阶段工作 |
|--------------------------------------|----------|-----------|
| 使用频率与时长区（含日均时长） | ✅ 有 usage_days + total_minutes | 增加日均时长计算 |
| 学科趋势变化区 | ✅ 有 subject_risks | 增加趋势图文字描述 |
| 风险与关注点区 | ❌ 缺失 | 新增高风险知识点摘要 + 反复错误点摘要 |
| 成绩与排名变化区 | ❌ 缺失 | 新增考试成绩变化表格（条件展示） |
| 家长支持建议区 | ❌ 缺失 | 新增 parent_support_suggestions |
| 周期选择器 | ❌ 缺失 | 复用 WeekSelector 组件 |
| 分享按钮 | ✅ 已有（但缺少完整交互） | 完善分享流程 |

**后端变更**：`services/report.py` — `build_weekly_report_payload()` 增强 `parent_view_content`

```python
parent_view_content = {
    "student_name": None,  # 由端点层填充
    "usage_days": usage_days,
    "total_minutes": total_minutes,
    "avg_daily_minutes": round(total_minutes / max(usage_days, 1)),
    "task_completion_rate": task_completion_rate,
    "subject_risks": [...],  # 现有
    "risk_summary": {
        "high_risk_points": [
            {"name": p["name"], "subject_name": p["subject_name"]}
            for p in high_risk_points[:3]
        ],
        "repeated_errors": [
            {"name": e["name"], "error_count": e["error_count"]}
            for e in repeated_error_points[:3]
        ],
    },
    "trend_description": suggestions[0] if suggestions else None,
    "action_suggestions": suggestions,
    "parent_support_suggestions": _generate_parent_suggestions(
        usage_days, task_completion_rate, subject_trends
    ),
}
```

**家长支持建议生成逻辑**：

```python
def _generate_parent_suggestions(
    usage_days: int,
    completion_rate: float,
    subject_trends: list[dict],
) -> list[str]:
    suggestions = []
    if usage_days >= 5:
        suggestions.append("孩子本周学习投入积极，建议给予肯定和鼓励。")
    elif usage_days >= 3:
        suggestions.append("孩子本周学习频率适中，可适当提醒保持节奏。")
    else:
        suggestions.append("孩子本周使用频率较低，建议了解原因并鼓励坚持。")

    declining = [s for s in subject_trends if s["trend"] == "declining"]
    if declining:
        suggestions.append(
            f"{declining[0]['subject_name']}近期表现有下滑趋势，"
            "如有需要可考虑针对性辅导。"
        )

    suggestions.append("周末可适当提醒孩子进行错题回顾。")
    return suggestions[:3]
```

**前端变更**：`parent/report/weekly/page.tsx` 增加以下区域：

1. **日均时长卡片**（第三个指标卡片）
2. **风险摘要区**：高风险知识点列表 + 反复错误点列表（仅名称，不展示详情，遵循 PRD §13.5 脱敏规则）
3. **考试成绩变化区**（条件展示，仅在有 ExamRecord 数据时显示）
4. **家长支持建议区**：独立卡片，列出 1-3 条建议

**前端类型变更**：`types/api.ts`

```typescript
export interface ParentWeeklyReport {
  // 现有字段...
  avg_daily_minutes?: number;
  risk_summary?: {
    high_risk_points: Array<{ name: string; subject_name: string }>;
    repeated_errors: Array<{ name: string; error_count: number }>;
  };
  parent_support_suggestions?: string[];
  score_changes?: Array<{
    subject_name: string;
    score: number;
    full_score: number;
    class_rank_change?: string;   // e.g. "12→8"
    grade_rank_change?: string;
  }>;
}
```

### 5.2 管理后台指标增强

#### 5.2.1 新增 4 个指标端点

所有端点支持 `period` 查询参数：`today`（默认）、`week`、`month`。

**1. GET /admin/metrics/costs — 成本趋势**

```python
class CostTrendOut(BaseModel):
    period: str  # "today" | "week" | "month"
    total_cost: float
    daily_avg_cost: float
    by_model: list[dict]  # [{"model": "qwen-turbo", "cost": 15.20}, ...]
    trend: list[dict]     # [{"date": "2026-03-20", "cost": 12.35}, ...]
```

**服务层实现**：

```python
async def get_cost_trend(
    db: AsyncSession, period: str = "today"
) -> dict:
    start_date = _period_start_date(period)

    # 总成本
    total_result = await db.execute(
        select(func.coalesce(func.sum(ModelCallLog.estimated_cost), 0))
        .where(ModelCallLog.created_at >= start_date)
    )
    total_cost = float(total_result.scalar())

    # 按模型分类
    by_model_result = await db.execute(
        select(ModelCallLog.model, func.sum(ModelCallLog.estimated_cost))
        .where(ModelCallLog.created_at >= start_date)
        .group_by(ModelCallLog.model)
        .order_by(func.sum(ModelCallLog.estimated_cost).desc())
    )
    by_model = [
        {"model": row[0], "cost": float(row[1] or 0)}
        for row in by_model_result.all()
    ]

    # 按天聚合趋势
    trend_result = await db.execute(
        select(
            func.date(ModelCallLog.created_at),
            func.sum(ModelCallLog.estimated_cost),
        )
        .where(ModelCallLog.created_at >= start_date)
        .group_by(func.date(ModelCallLog.created_at))
        .order_by(func.date(ModelCallLog.created_at))
    )
    trend = [
        {"date": str(row[0]), "cost": float(row[1] or 0)}
        for row in trend_result.all()
    ]

    days = max(len(trend), 1)
    return {
        "period": period,
        "total_cost": round(total_cost, 2),
        "daily_avg_cost": round(total_cost / days, 2),
        "by_model": by_model,
        "trend": trend,
    }
```

**2. GET /admin/metrics/fallbacks — 降级统计**

```python
class FallbackStatsOut(BaseModel):
    period: str
    total_calls: int
    fallback_count: int
    fallback_rate: float          # 0.0 ~ 1.0
    by_reason: list[dict]         # [{"reason": "timeout", "count": 14}, ...]
    trend: list[dict]             # [{"date": "...", "fallback_rate": 0.025}, ...]
```

**服务层逻辑**：
- `total_calls`：`ModelCallLog` 按时间范围 count
- `fallback_count`：`where(is_fallback == True)` count
- `by_reason`：从 `error_message` 字段提取分类（timeout / rate_limit / service_error / other）
- `trend`：按天聚合降级率

**降级原因提取规则**：

```python
def _classify_fallback_reason(error_message: str | None) -> str:
    if not error_message:
        return "unknown"
    msg = error_message.lower()
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "rate" in msg or "429" in msg or "limit" in msg:
        return "rate_limit"
    if "500" in msg or "502" in msg or "503" in msg or "service" in msg:
        return "service_error"
    return "other"
```

**3. GET /admin/metrics/errors — 错误统计**

```python
class ErrorStatsOut(BaseModel):
    period: str
    total_errors: int
    by_type: list[dict]           # [{"type": "model_error", "count": 4}, ...]
    by_agent: list[dict]          # [{"agent": "tutoring", "error_count": 3}, ...]
    trend: list[dict]             # [{"date": "...", "error_count": 2}, ...]
```

**服务层逻辑**：
- 错误 = `ModelCallLog.success == False`
- `by_type`：从 `error_message` 提取分类（api_error / model_error / timeout / parse_error / other）
- `by_agent`：按 `agent_name` 分组统计错误次数

**4. GET /admin/metrics/latency — 延迟分位数**

```python
class LatencyStatsOut(BaseModel):
    period: str
    avg_latency_ms: int
    p95_latency_ms: int
    p99_latency_ms: int
    by_agent: list[dict]          # [{"agent": "tutoring", "avg_ms": 3200, "p95_ms": 5100}, ...]
```

**服务层逻辑**：

```python
async def get_latency_stats(
    db: AsyncSession, period: str = "today"
) -> dict:
    start_date = _period_start_date(period)

    # PostgreSQL percentile_cont
    from sqlalchemy import text

    result = await db.execute(
        text("""
            SELECT
                COALESCE(AVG(latency_ms), 0)::int,
                COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0)::int,
                COALESCE(percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms), 0)::int
            FROM model_call_logs
            WHERE created_at >= :start_date AND success = true
        """),
        {"start_date": start_date},
    )
    row = result.one()

    # 按 Agent 分组
    by_agent_result = await db.execute(
        text("""
            SELECT
                agent_name,
                AVG(latency_ms)::int,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)::int
            FROM model_call_logs
            WHERE created_at >= :start_date AND success = true
            GROUP BY agent_name
        """),
        {"start_date": start_date},
    )

    return {
        "period": period,
        "avg_latency_ms": row[0],
        "p95_latency_ms": row[1],
        "p99_latency_ms": row[2],
        "by_agent": [
            {"agent": r[0], "avg_ms": r[1], "p95_ms": r[2]}
            for r in by_agent_result.all()
        ],
    }
```

#### 5.2.2 辅助函数

```python
from datetime import date, datetime, timedelta, UTC

def _period_start_date(period: str) -> datetime:
    today = date.today()
    if period == "week":
        start = today - timedelta(days=today.weekday())
    elif period == "month":
        start = today.replace(day=1)
    else:  # today
        start = today
    return datetime.combine(start, datetime.min.time(), tzinfo=UTC)
```

#### 5.2.3 仪表盘增强

**管理仪表盘**（`/admin/dashboard`）新增内容：

1. **模型调用摘要卡片组**（3 个卡片）

```
┌────────────────┐ ┌────────────────┐ ┌──────────────┐
│ 📞 调用次数    │ │ 💰 今日成本    │ │ ⚠️ 降级率    │
│                │ │                │ │              │
│    156 次      │ │   ¥12.35      │ │    2.5%      │
│  ↑ 较昨日+23   │ │  ↓ 较昨日-¥3   │ │  正常范围    │
└────────────────┘ └────────────────┘ └──────────────┘
```

数据来源：
- 调用次数：`GET /admin/metrics/model-calls` → `total`
- 今日成本：`GET /admin/metrics/costs?period=today` → `total_cost`
- 降级率：`GET /admin/metrics/fallbacks?period=today` → `fallback_rate`

2. **待处理事项分类计数**

```
┌────────────────────────────────────────────────────┐
│  🔴 OCR 识别失败         3 条     [ 去处理 → ]      │
│  🟡 计划异常             1 条     [ 去处理 → ]      │
│  🟡 知识点标注待修正     2 条     [ 去处理 → ]      │
└────────────────────────────────────────────────────┘
```

新增端点：`GET /admin/corrections/pending/count`

```python
async def get_pending_count_by_type(db: AsyncSession) -> dict:
    result = await db.execute(
        select(ManualCorrection.target_type, func.count(ManualCorrection.id))
        .where(ManualCorrection.status == "pending")
        .group_by(ManualCorrection.target_type)
    )
    counts = {row[0]: row[1] for row in result.all()}
    return {
        "ocr": counts.get("ocr", 0),
        "knowledge": counts.get("knowledge", 0),
        "plan": counts.get("plan", 0),
        "total": sum(counts.values()),
    }
```

### 5.3 纠偏流程完善

#### 5.3.1 纠偏详情面板

当前纠偏页面仅有列表视图，管理员只能看到类型 + target_id + corrected_content JSON。需要增加右侧详情面板，根据纠偏类型展示不同内容。

**桌面端布局变更**：

```
┌─────────────────────────────┬────────────────────────┐
│ 待处理列表                  │ 纠偏操作               │
│                             │                        │
│ ┌─────────────────────────┐ │ [根据类型切换面板内容]  │
│ │ 🔴 OCR 识别失败 #1234  │ │                        │
│ └─────────────────────────┘ │ OCR → 图片预览+修正框  │
│                             │ Knowledge → 状态选择器  │
│ ┌─────────────────────────┐ │ Plan → 学科/任务调整    │
│ │ 🟡 知识点标注 #1235    │ │                        │
│ └─────────────────────────┘ │ [ 提交修正 ] [跳过]    │
│                             │                        │
└─────────────────────────────┴────────────────────────┘
```

**GET /admin/corrections/{id} — 纠偏详情端点**：

```python
class CorrectionDetailOut(BaseModel):
    id: int
    target_type: str
    target_id: int
    original_content: dict | None
    corrected_content: dict
    correction_reason: str | None
    corrected_by: int
    status: str
    created_at: datetime | None

    # 上下文数据（根据 target_type 填充）
    context: dict | None = None
```

**服务层逻辑**：

```python
async def get_correction_detail(
    db: AsyncSession, correction_id: int
) -> dict:
    correction = await _get_correction(db, correction_id)
    context = {}

    if correction.target_type == "ocr":
        upload = await db.execute(
            select(StudyUpload).where(StudyUpload.id == correction.target_id)
        )
        upload_obj = upload.scalar_one_or_none()
        if upload_obj:
            context = {
                "original_url": upload_obj.original_url,
                "thumbnail_url": upload_obj.thumbnail_url,
                "upload_type": upload_obj.upload_type,
                "ocr_result": upload_obj.ocr_result,
                "ocr_error": upload_obj.ocr_error,
            }
    elif correction.target_type == "knowledge":
        original = correction.original_content or {}
        sid = original.get("student_id")
        kpid = original.get("knowledge_point_id")
        if sid and kpid:
            # 获取知识点名称和学科
            kp_result = await db.execute(
                select(KnowledgeTree.name, Subject.name)
                .join(Subject, KnowledgeTree.subject_id == Subject.id)
                .where(KnowledgeTree.id == kpid)
            )
            kp_row = kp_result.one_or_none()
            if kp_row:
                context = {
                    "knowledge_point_name": kp_row[0],
                    "subject_name": kp_row[1],
                    "current_status": original.get("status"),
                }
    elif correction.target_type == "plan":
        plan = await db.execute(
            select(DailyPlan)
            .options(selectinload(DailyPlan.tasks))
            .where(DailyPlan.id == correction.target_id)
        )
        plan_obj = plan.scalar_one_or_none()
        if plan_obj:
            context = {
                "plan_date": str(plan_obj.plan_date),
                "learning_mode": plan_obj.learning_mode,
                "tasks": [
                    {
                        "id": t.id,
                        "subject_id": t.subject_id,
                        "task_type": t.task_type,
                        "task_content": t.task_content,
                        "sequence": t.sequence,
                    }
                    for t in plan_obj.tasks
                ],
            }

    return {
        **CorrectionOut.model_validate(correction).model_dump(),
        "context": context,
    }
```

#### 5.3.2 OCR 纠偏面板

**组件**：`OcrCorrectionPanel`

```
┌────────────────────────────────────┐
│ 📷 原始图片                        │
│ ┌──────────────────────────────┐   │
│ │                              │   │
│ │    [img src=original_url]    │   │
│ │                              │   │
│ └──────────────────────────────┘   │
│                                    │
│ 📝 当前 OCR 结果                   │
│ ┌──────────────────────────────┐   │
│ │ {ocr_result JSON 展示}       │   │
│ └──────────────────────────────┘   │
│                                    │
│ ✏️ 修正内容                        │
│ ┌──────────────────────────────┐   │
│ │ [textarea: 输入修正后的文本]  │   │
│ └──────────────────────────────┘   │
│                                    │
│ 📋 修正原因                        │
│ ┌──────────────────────────────┐   │
│ │ [select: 图片模糊 | 手写识别  │   │
│ │  错误 | 格式复杂 | 其他]     │   │
│ └──────────────────────────────┘   │
│                                    │
│ [ 提交修正 ]          [ 跳过 ]     │
└────────────────────────────────────┘
```

**数据流**：
1. 选中列表项 → 调用 `GET /admin/corrections/{id}` 获取详情
2. `context.original_url` 渲染图片预览
3. `context.ocr_result` 渲染当前 OCR 结果
4. 管理员编辑修正内容 + 选择原因
5. 点击「提交修正」→ 调用 `POST /admin/corrections/{id}/resolve`
6. 刷新列表

#### 5.3.3 知识点纠偏面板

**组件**：`KnowledgeCorrectionPanel`

```
┌────────────────────────────────────┐
│ 📚 知识点信息                      │
│ ┌──────────────────────────────┐   │
│ │ 学科：数学                    │   │
│ │ 知识点：函数的单调性判断       │   │
│ │ 当前状态：需要巩固             │   │
│ └──────────────────────────────┘   │
│                                    │
│ ✏️ 修正为                          │
│ ┌──────────────────────────────┐   │
│ │ ○ 未观察                      │   │
│ │ ○ 初步接触                    │   │
│ │ ● 基本掌握 ←                  │   │
│ │ ○ 需要巩固                    │   │
│ │ ○ 反复失误                    │   │
│ └──────────────────────────────┘   │
│                                    │
│ 📋 修正原因                        │
│ ┌──────────────────────────────┐   │
│ │ [输入修正原因]                │   │
│ └──────────────────────────────┘   │
│                                    │
│ [ 提交修正 ]          [ 跳过 ]     │
└────────────────────────────────────┘
```

**知识点状态选项**（与后端枚举对齐）：

```typescript
const KNOWLEDGE_STATUS_OPTIONS = [
  { value: "未观察", label: "未观察" },
  { value: "初步接触", label: "初步接触" },
  { value: "基本掌握", label: "基本掌握" },
  { value: "需要巩固", label: "需要巩固" },
  { value: "反复失误", label: "反复失误" },
];
```

#### 5.3.4 计划纠偏

**新增后端支持**：

```python
class PlanCorrectionRequest(BaseModel):
    plan_id: int
    corrected_tasks: list[dict]  # 调整后的任务列表
    reason: str | None = None

async def correct_plan(
    db: AsyncSession,
    admin_user_id: int,
    plan_id: int,
    corrected_tasks: list[dict],
    reason: str | None,
) -> ManualCorrection:
    plan_result = await db.execute(
        select(DailyPlan)
        .options(selectinload(DailyPlan.tasks))
        .where(DailyPlan.id == plan_id)
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise AppError("PLAN_NOT_FOUND", "计划不存在", status_code=404)

    original_tasks = [
        {
            "id": t.id,
            "subject_id": t.subject_id,
            "task_type": t.task_type,
            "task_content": t.task_content,
            "sequence": t.sequence,
        }
        for t in plan.tasks
    ]

    correction = ManualCorrection(
        target_type="plan",
        target_id=plan_id,
        original_content={"tasks": original_tasks},
        corrected_content={"tasks": corrected_tasks},
        correction_reason=reason,
        corrected_by=admin_user_id,
        status="pending",
    )
    db.add(correction)
    await db.flush()
    return correction
```

**说明**：计划纠偏提交后状态为 `pending`，管理员需要二次确认 resolve 后才真正修改计划。这与 OCR/Knowledge 的直接修正模式不同，因为计划调整影响学生当日学习流程，需要更谨慎。

#### 5.3.5 修正历史记录

**新增端点**：`GET /admin/corrections/logs`

```python
async def get_correction_logs(
    db: AsyncSession, page: int, page_size: int
) -> tuple[list[ManualCorrection], int]:
    resolved_filter = ManualCorrection.status == "resolved"
    count_result = await db.execute(
        select(func.count(ManualCorrection.id)).where(resolved_filter)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ManualCorrection)
        .where(resolved_filter)
        .order_by(ManualCorrection.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return result.scalars().all(), total
```

**前端组件**：`CorrectionLogList`

```
┌────────────────────────────────────────────────────┐
│ 📜 最近修正记录                                      │
│ ┌────────────────────────────────────────────────┐  │
│ │ #1230 OCR修正    3.17 10:15   已处理            │  │
│ │ #1228 知识点修正  3.16 18:20   已处理            │  │
│ │ #1225 计划调整    3.15 09:30   已处理            │  │
│ └────────────────────────────────────────────────┘  │
│                              [加载更多]              │
└────────────────────────────────────────────────────┘
```

### 5.4 监控统计页面增强

#### 5.4.1 页面布局变更

当前 `/admin/metrics` 页面只有 4 个基础卡片。需要增强为完整的 6 区域布局：

```
┌────────────────────────────────────────────────────────┐
│ 📊 监控统计                        [ 今日 | 本周 | 本月 ] │
├────────────────────────────────────────────────────────┤
│                                                        │
│ 🤖 模型调用统计                                         │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 总调用: 1,234    Token消耗: 2.5M                    │ │
│ │ ┌──────────────────────────────────────────────┐   │ │
│ │ │ Agent     调用次数   平均延迟   Token消耗     │   │ │
│ │ │ Extract.    456      2.1s      800K          │   │ │
│ │ │ Planning    234      1.8s      500K          │   │ │
│ │ │ Tutoring    389      3.2s      900K          │   │ │
│ │ │ Assess.     155      0.8s      300K          │   │ │
│ │ └──────────────────────────────────────────────┘   │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ ┌─────────────────────────┐ ┌─────────────────────────┐│
│ │ 💰 成本追踪             │ │ ⚠️ 降级统计              ││
│ │ 累计: ¥86.50           │ │ 降级次数: 31 次          ││
│ │ 日均: ¥12.35           │ │ 降级率: 2.5%            ││
│ │ 按模型: Qwen ¥15.20   │ │ 原因: 超时45% 限流30%   ││
│ └─────────────────────────┘ └─────────────────────────┘│
│                                                        │
│ ┌─────────────────────────┐ ┌─────────────────────────┐│
│ │ ❌ 错误统计             │ │ ⚡ 性能指标              ││
│ │ 错误总数: 12            │ │ 平均延迟: 1.8s          ││
│ │ API错误: 5              │ │ P95: 3.2s               ││
│ │ 模型错误: 4             │ │ P99: 5.1s               ││
│ │ 超时: 3                 │ │ 按Agent分组列表          ││
│ └─────────────────────────┘ └─────────────────────────┘│
└────────────────────────────────────────────────────────┘
```

#### 5.4.2 时间范围联动

时间范围选择器切换后，所有数据需要联动刷新。

**SWR Hooks 设计**：

```typescript
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
```

**TypeScript 类型**：

```typescript
export interface CostTrendData {
  period: string;
  total_cost: number;
  daily_avg_cost: number;
  by_model: Array<{ model: string; cost: number }>;
  trend: Array<{ date: string; cost: number }>;
}

export interface FallbackStatsData {
  period: string;
  total_calls: number;
  fallback_count: number;
  fallback_rate: number;
  by_reason: Array<{ reason: string; count: number }>;
  trend: Array<{ date: string; fallback_rate: number }>;
}

export interface ErrorStatsData {
  period: string;
  total_errors: number;
  by_type: Array<{ type: string; count: number }>;
  by_agent: Array<{ agent: string; error_count: number }>;
  trend: Array<{ date: string; error_count: number }>;
}

export interface LatencyStatsData {
  period: string;
  avg_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  by_agent: Array<{ agent: string; avg_ms: number; p95_ms: number }>;
}
```

#### 5.4.3 图表方案

MVP 阶段不引入图表库（避免依赖膨胀），使用以下替代方案：

1. **成本趋势**：表格列表 + 数值展示（date → cost），日后可升级为 Recharts 折线图
2. **降级原因分布**：Badge 列表 + 百分比（reason → percentage），日后可升级为饼图
3. **延迟分布**：纯数值展示（avg / P95 / P99）+ 按 Agent 表格

**设计决策**：首期用户仅运营者 1 人，表格+数值即可满足监控需求。图表可作为后续优化项引入 Recharts。

---

## 6. 实施步骤

| 步骤 | 内容 | 新增/修改文件 | 验证方式 |
|------|------|--------------|----------|
| **1** | 后端：指标 schema + 4 个指标服务函数 | `schemas/admin.py`, `services/admin.py` | `ruff check` 通过 |
| **2** | 后端：4 个指标端点注册 | `api/v1/endpoints/admin.py` | Swagger 可访问 |
| **3** | 后端：纠偏详情 + 日志 + 计划纠偏 + 分类计数服务 | `services/admin.py` | 单元测试 |
| **4** | 后端：4 个纠偏端点注册 | `api/v1/endpoints/admin.py` | Swagger 可访问 |
| **5** | 后端：周报增强（上周对比 + 家长支持建议） | `services/report.py`, `schemas/report.py` | 对比数据正确 |
| **6** | 前端：WeekSelector 组件 | `components/report/week-selector.tsx` | 显示最近 8 周 |
| **7** | 前端：学生周报页面增强 | `report/weekly/page.tsx` | 周期切换 + 对比指标 |
| **8** | 前端：家长周报页面增强 | `parent/report/weekly/page.tsx` | 风险摘要 + 建议 |
| **9** | 前端：新增 hooks + types | `hooks.ts`, `types/api.ts` | tsc 编译通过 |
| **10** | 前端：监控统计页面增强 | `admin/metrics/page.tsx` | 6 区域布局 + 联动 |
| **11** | 前端：仪表盘增强 | `admin/dashboard/page.tsx` | 成本+降级+分类计数 |
| **12** | 前端：纠偏详情面板 | `admin/corrections/page.tsx` + 3 个面板组件 | 双栏布局 + 面板切换 |
| **13** | 前端：修正历史记录 | `admin/corrections/page.tsx` | 已处理列表可查 |
| **14** | 全量验证 | — | ruff + tsc + 冒烟测试 |

---

## 7. API 路径汇总

### 7.1 新增端点（8 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/metrics/costs?period={period}` | 成本趋势 |
| GET | `/admin/metrics/fallbacks?period={period}` | 降级统计 |
| GET | `/admin/metrics/errors?period={period}` | 错误统计 |
| GET | `/admin/metrics/latency?period={period}` | 延迟分位数 |
| GET | `/admin/corrections/{id}` | 纠偏项详情 |
| GET | `/admin/corrections/logs?page={page}&page_size={size}` | 修正历史 |
| POST | `/admin/corrections/plan` | 提交计划纠偏 |
| GET | `/admin/corrections/pending/count` | 按类型统计待处理数 |

### 7.2 修改的端点（2 个）

| 方法 | 路径 | 变更 |
|------|------|------|
| GET | `/student/report/weekly` | 响应增加 previous_* 对比字段 |
| GET | `/parent/report/weekly` | 响应增加 risk_summary, parent_support_suggestions, avg_daily_minutes |

---

## 8. 前后端类型新增汇总

### 8.1 后端 Schema（`schemas/admin.py` 新增）

```python
class CostTrendOut(BaseModel):
    period: str
    total_cost: float
    daily_avg_cost: float
    by_model: list[dict]
    trend: list[dict]

class FallbackStatsOut(BaseModel):
    period: str
    total_calls: int
    fallback_count: int
    fallback_rate: float
    by_reason: list[dict]
    trend: list[dict]

class ErrorStatsOut(BaseModel):
    period: str
    total_errors: int
    by_type: list[dict]
    by_agent: list[dict]
    trend: list[dict]

class LatencyStatsOut(BaseModel):
    period: str
    avg_latency_ms: int
    p95_latency_ms: int
    p99_latency_ms: int
    by_agent: list[dict]

class CorrectionDetailOut(CorrectionOut):
    context: dict | None = None

class PendingCountByTypeOut(BaseModel):
    ocr: int = 0
    knowledge: int = 0
    plan: int = 0
    total: int = 0

class PlanCorrectionRequest(BaseModel):
    plan_id: int
    corrected_tasks: list[dict]
    reason: str | None = None
```

### 8.2 前端类型（`types/api.ts` 新增）

```typescript
// 管理端指标
export interface CostTrendData { ... }        // 见 §5.4.2
export interface FallbackStatsData { ... }
export interface ErrorStatsData { ... }
export interface LatencyStatsData { ... }

// 纠偏详情
export interface CorrectionDetail extends CorrectionItem {
  context: Record<string, unknown> | null;
}

// 待处理分类计数
export interface PendingCountByType {
  ocr: number;
  knowledge: number;
  plan: number;
  total: number;
}
```

---

## 9. 设计决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 延迟分位数计算 | PostgreSQL `percentile_cont` 原生函数 | 避免应用层排序大量数据；PostgreSQL 15 原生支持 |
| 降级原因分类 | 从 `error_message` 字段关键词匹配 | 无需新增字段或枚举；MVP 足够；后续可迁移到结构化 `error_code` |
| 图表方案 | 表格+数值，不引入图表库 | 首期仅 1 人使用管理后台，表格够用；避免引入 Recharts 增加打包体积；后续可平滑升级 |
| 计划纠偏确认模式 | 提交后 `pending`，需 resolve 确认 | 计划调整影响学生当日学习流程，需二次确认；与 OCR/Knowledge 的直接修正模式区分 |
| 周期选择器数据 | 前端计算最近 8 周 | 纯日期计算无需后端支持；减少 API 调用 |
| 上周对比数据 | 后端计算并返回 previous_* 字段 | 前端无需额外请求上周数据；一次请求获取完整展示数据 |
| 家长支持建议 | 规则引擎生成，非 LLM | MVP 阶段建议内容可预测且有限，规则引擎够用；节省 LLM 成本 |

---

## 10. 验证方案

### 10.1 逐步验证

每步完成后：
- `ruff check app/` — Python 代码质量
- `npx tsc --noEmit` — TypeScript 类型检查
- 该模块 Swagger 端点可访问（后端步骤）
- 页面可正常渲染（前端步骤）

### 10.2 集成冒烟测试

1. **周报流程**：切换周期 → 查看不同周数据 → 对比指标正确 → 生成分享链接 → 分享页可访问
2. **家长周报流程**：查看周报 → 风险摘要显示 → 支持建议显示 → 切换周期 → 生成分享链接
3. **管理仪表盘**：查看今日概览 → 成本+降级率显示 → 待处理分类计数 → 点击「去处理」跳转
4. **纠偏流程**：选择待处理项 → 右侧面板展示详情 → 提交修正 → 列表刷新 → 历史记录显示
5. **监控统计**：切换时间范围（今日/本周/本月） → 所有数据联动刷新 → 数值合理

### 10.3 权限验证

- 学生访问 `/admin/metrics/costs` → 403
- 家长访问 `/admin/corrections/logs` → 403
- 未登录访问管理端点 → 401

### 10.4 数据一致性

- `costs.total_cost` = `sum(by_model[].cost)`
- `fallbacks.fallback_rate` = `fallback_count / total_calls`
- `pending/count.total` = `sum(ocr + knowledge + plan)`
- 上周对比数据与实际上周周报一致
