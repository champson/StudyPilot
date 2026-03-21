# Phase 6 详细设计：测试完善与生产部署

> **状态**：待实施
> **创建日期**：2026-03-21

## 1. 目标与范围

在 Phase 1-5 完成全部功能开发后，Phase 6 聚焦于：将系统从开发状态推进到 MVP 生产可用状态。

**范围边界**：
- 本阶段聚焦于测试完善、CI/CD 流水线、生产部署配置、安全加固
- 不包含新业务功能开发
- 不包含考试冲刺模式（P1）
- 不包含云服务商专属集成（阿里云 OSS 等），仅准备通用部署方案

**交付物**：
1. Phase 5 新增 API 的完整测试覆盖（admin 指标、纠偏详情、周报对比）
2. 端到端冒烟测试（核心 happy path）
3. 安全测试（越权访问、JWT 伪造、文件类型校验）
4. GitHub Actions CI 流水线（lint + test + build）
5. 生产级 Docker 配置（多阶段构建、Nginx 反向代理、Celery Beat）
6. Alembic 自动迁移、健康检查增强、结构化日志

---

## 2. 现状分析

### 2.1 测试覆盖现状

| 模块 | 测试文件 | 测试数 | 覆盖缺口 |
|------|----------|--------|----------|
| Auth | test_auth.py | 4 | ✅ 足够 |
| Permissions | test_permissions.py | 3 | 缺少跨用户数据隔离测试 |
| Plan | test_plan.py | 7 | ✅ 足够 |
| Upload | test_upload.py | 4 | ✅ 足够 |
| QA | test_qa.py | 5 | ✅ 足够 |
| Error Book | test_error_book.py | 4 | ✅ 足够 |
| Knowledge | test_knowledge.py | ? | 需确认 |
| Report | test_report.py | 2 | ❌ 缺少周报对比、家长建议测试 |
| Admin | test_admin.py | 6 | ❌ 缺少 Phase 5 指标端点测试 |
| Share | test_share.py | ? | 需确认 |
| Parent | test_parent.py | ? | 需确认 |
| LLM Agents | 5 个测试文件 | ~10 | ✅ 足够 |

### 2.2 部署基础设施现状

| 组件 | 当前状态 | 缺口 |
|------|----------|------|
| Dockerfile | ✅ 基础可用 | 无多阶段构建、以 root 运行 |
| docker-compose.yml | ✅ 开发环境 | 缺 Celery Beat、Nginx、生产配置 |
| CI/CD | ❌ 无 | 需 GitHub Actions |
| Nginx | ❌ 无 | 需反向代理 + 静态文件服务 |
| Alembic 自动迁移 | ❌ 手动 | 需启动时自动执行 |
| 日志 | ❌ print 级别 | 需结构化 JSON 日志 |
| 健康检查 | ⚠️ 基础 | 仅返回 `{"status": "ok"}`，不检查 DB/Redis |

---

## 3. 新增与修改文件清单

### 3.1 测试文件（新增）

```
server/tests/
├── test_admin_metrics.py          # Phase 5 指标端点测试
├── test_admin_corrections_ext.py  # 纠偏详情/日志/计划纠偏测试
├── test_report_comparison.py      # 周报对比 + 家长建议测试
├── test_security.py               # 安全测试（越权、JWT、文件类型）
└── test_smoke.py                  # 端到端冒烟测试（核心 happy path）
```

### 3.2 部署配置文件（新增）

```
server/
├── Dockerfile.prod                # 生产级多阶段构建
├── docker-compose.prod.yml        # 生产 Docker Compose
├── nginx/
│   └── nginx.conf                 # Nginx 反向代理配置
├── scripts/
│   └── start.sh                   # 启动脚本（迁移 + uvicorn）
└── .env.production                # 生产环境变量模板

.github/
└── workflows/
    └── ci.yml                     # GitHub Actions CI
```

### 3.3 修改的已有文件

| 文件 | 变更内容 |
|------|---------|
| `server/app/main.py` | 增加结构化日志配置、startup 事件 |
| `server/app/api/v1/endpoints/health.py` | 增强健康检查（DB + Redis 连通性） |
| `server/docker-compose.yml` | 增加 Celery Beat 服务 |
| `server/Dockerfile` | 增加非 root 用户 |
| `server/requirements.txt` | 增加 `pytest-cov`、`locust` |

---

## 4. 测试设计

### 4.1 Phase 5 指标端点测试 (`test_admin_metrics.py`)

```python
# 测试覆盖：
# 1. GET /admin/metrics/costs — 成本趋势（空数据、有数据、period 参数）
# 2. GET /admin/metrics/fallbacks — 降级统计（空数据、有数据）
# 3. GET /admin/metrics/errors — 错误统计（空数据、有数据）
# 4. GET /admin/metrics/latency — 延迟分位数（空数据、有数据）
# 5. 非法 period 参数 → 400
# 6. 非 admin 角色 → 403
```

**测试策略**：
- 使用 `seed_data` fixture 中的 admin_token
- 先测试空数据返回（零值默认），确保端点不崩溃
- 插入 `ModelCallLog` 测试数据，验证聚合计算正确性
- 验证 `period` 参数过滤逻辑（today/week/month）
- 验证非法 period 返回 400

### 4.2 纠偏扩展测试 (`test_admin_corrections_ext.py`)

```python
# 测试覆盖：
# 1. GET /admin/corrections/{id} — 获取详情（OCR 类型含 context）
# 2. GET /admin/corrections/{id} — 获取详情（knowledge 类型含 context）
# 3. GET /admin/corrections/{id} — 不存在的 ID → 404
# 4. GET /admin/corrections/logs — 修正历史分页
# 5. GET /admin/corrections/pending/count — 按类型计数
# 6. POST /admin/corrections/plan — 提交计划纠偏
# 7. POST /admin/corrections/{id}/resolve — resolve 计划纠偏（含任务匹配）
# 8. POST /admin/corrections/{id}/resolve — 计划纠偏无法匹配任务 → 400
```

**测试策略**：
- 创建 `ManualCorrection` + 关联的 `StudyUpload` / `KnowledgePointMastery` 测试数据
- 验证 `context` 字段根据 `target_type` 正确填充
- 创建 `DailyPlan` + `PlanTask` 测试计划纠偏的任务匹配逻辑
- 验证 fail-closed：不可匹配的任务导致 400 错误

### 4.3 周报对比测试 (`test_report_comparison.py`)

```python
# 测试覆盖：
# 1. 当前周有报告、上周有报告 → previous_* 字段正确
# 2. 当前周有报告、上周无报告 → previous_* 为 null
# 3. W01 回退到上一年 W52/W53 — ISO 8601 边界正确
# 4. 家长周报包含 parent_support_suggestions
# 5. 家长周报包含 risk_summary
# 6. 家长周报 avg_daily_minutes 计算正确
```

**测试策略**：
- 手动创建 `WeeklyReport` 数据（当前周 + 上周）
- 通过 API 端点验证 `previous_*` 字段
- 特别测试 W01 → W52/W53 的年边界处理

### 4.4 安全测试 (`test_security.py`)

```python
# 测试覆盖：
# 1. 学生 A 不能访问学生 B 的计划
# 2. 学生 A 不能访问学生 B 的错题
# 3. 学生 A 不能访问学生 B 的 QA 会话
# 4. 家长只能访问关联学生的数据
# 5. 伪造 JWT payload（篡改 student_id）→ 403/401
# 6. 过期分享链接 → 401/410
# 7. 文件上传类型校验（仅允许 jpg/png/webp）
```

**测试策略**：
- 创建第二个学生用户（student_user_b + profile_b），分别生成 JWT
- 用学生 B 的 token 尝试访问学生 A 的数据
- 构造伪造 token（修改 student_id claim）
- 上传非图片文件验证拒绝

### 4.5 端到端冒烟测试 (`test_smoke.py`)

```python
# 完整 happy path 测试：
# 1. 登录 → 获取 token
# 2. 创建学生档案 → 提交入学问卷
# 3. 生成今日计划
# 4. 更新任务状态（pending → entered → executed → completed）
# 5. 上传学习材料
# 6. 发起答疑（同步 + 流式）
# 7. 查看错题列表 + 错题召回
# 8. 查看知识点状态
# 9. 查看周报（无数据 → 404）
# 10. 管理员查看指标 + 纠偏列表
```

**设计决策**：使用 httpx AsyncClient 而非 Playwright，因为后端 API 测试足以验证核心闭环，前端 E2E 测试可在后续版本引入。

---

## 5. CI/CD 流水线设计

### 5.1 GitHub Actions CI (`ci.yml`)

```yaml
触发条件：
  - push to main
  - pull_request to main

Job 1: lint-and-type-check
  - Python: ruff check + ruff format --check
  - TypeScript: tsc --noEmit + next lint

Job 2: backend-test
  - 依赖: PostgreSQL 15 service container + Redis 7 service container
  - 步骤:
    1. pip install -r requirements.txt
    2. alembic upgrade head
    3. pytest --cov=app --cov-report=xml -x
  - 产物: coverage report

Job 3: frontend-build
  - 步骤:
    1. npm ci
    2. npm run build
```

**设计决策**：
- 不在 CI 中运行前端 E2E 测试（MVP 阶段无需 Playwright）
- 使用 GitHub Actions service container 而非 docker-compose（更快、更可控）
- `-x` 参数让测试在首次失败时停止（快速反馈）

### 5.2 流水线阶段

```
push/PR → lint → test (parallel) → build
              ↓         ↓
          ruff/tsc   pytest+pg+redis
```

---

## 6. 生产部署配置

### 6.1 Dockerfile.prod（多阶段构建）

```dockerfile
# Stage 1: 依赖安装
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: 运行环境
FROM python:3.11-slim
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
RUN chown -R app:app /app
USER app
EXPOSE 8000
CMD ["./scripts/start.sh"]
```

**优化点**：
- 非 root 用户运行
- 多阶段构建减小镜像体积
- 依赖层缓存优化

### 6.2 启动脚本 (`scripts/start.sh`)

```bash
#!/bin/bash
set -e

# 1. 运行数据库迁移
echo "Running database migrations..."
alembic upgrade head

# 2. 创建管理员账户（如不存在）
echo "Ensuring admin user..."
python -c "
import asyncio
from app.core.database import async_session_factory
from app.services.auth import ensure_admin_user
asyncio.run(ensure_admin_user())
"

# 3. 启动 uvicorn
echo "Starting API server..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers ${WORKERS:-2} \
  --log-level ${LOG_LEVEL:-info}
```

### 6.3 Nginx 配置

```nginx
功能：
- 反向代理 API 到 FastAPI (port 8000)
- 静态文件服务 (Next.js export 或 /uploads)
- SSL 终止（预留）
- 请求大小限制 (10MB for uploads)
- SSE 支持 (proxy_buffering off for /qa/chat/stream)
- 健康检查代理
```

### 6.4 docker-compose.prod.yml

```yaml
服务：
- db: PostgreSQL 15 (持久化卷 + 资源限制)
- redis: Redis 7 (持久化 + 资源限制)
- api: FastAPI (多阶段 Dockerfile + 环境变量 + 健康检查)
- worker: Celery worker (同镜像不同 CMD)
- beat: Celery beat (周报定时任务调度)
- nginx: Nginx 反向代理 (80/443 端口)
```

**新增 beat 服务**：当前 docker-compose.yml 缺少 Celery Beat，周报定时任务无法触发。

### 6.5 健康检查增强

当前 `/health` 仅返回 `{"status": "ok"}`。增强为深度健康检查：

```python
@app.get("/health")
async def health_check():
    checks = {}
    # DB 连通性
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Redis 连通性
    try:
        redis = get_redis_client()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503
    return JSONResponse(
        {"status": "ok" if all_ok else "degraded", "checks": checks},
        status_code=status_code
    )
```

### 6.6 结构化日志

```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)
```

**配置策略**：
- 生产环境：JSON 格式，INFO 级别
- 开发环境：标准格式，DEBUG 级别
- 通过 `DEBUG` 环境变量控制

---

## 7. 实施步骤

| 步骤 | 内容 | 新增/修改文件 | 验证方式 |
|------|------|--------------|----------|
| **1** | 测试：Phase 5 指标端点测试 | `test_admin_metrics.py` | pytest 通过 |
| **2** | 测试：纠偏扩展测试 | `test_admin_corrections_ext.py` | pytest 通过 |
| **3** | 测试：周报对比测试 | `test_report_comparison.py` | pytest 通过 |
| **4** | 测试：安全测试 | `test_security.py` | pytest 通过 |
| **5** | 测试：冒烟测试 | `test_smoke.py` | pytest 通过 |
| **6** | 部署：健康检查增强 | 修改 `main.py` + 新增 `endpoints/health.py` | `/health` 返回 DB+Redis 状态 |
| **7** | 部署：结构化日志 | 修改 `main.py` + 新增 `core/logging.py` | JSON 日志输出 |
| **8** | 部署：Dockerfile.prod + start.sh | 新增 2 文件 | `docker build` 成功 |
| **9** | 部署：Nginx 配置 | 新增 `nginx/nginx.conf` | 配置语法检查 |
| **10** | 部署：docker-compose.prod.yml | 新增 1 文件 | 配置结构正确 |
| **11** | 部署：docker-compose.yml 增加 beat | 修改已有文件 | beat 服务定义正确 |
| **12** | CI：GitHub Actions | 新增 `.github/workflows/ci.yml` | YAML 语法正确 |
| **13** | 依赖：requirements.txt 更新 | 修改已有文件 | pip install 成功 |
| **14** | 最终验证 | — | `ruff check` + `pytest` + `tsc` 全部通过 |

---

## 8. 测试用例汇总

### 8.1 test_admin_metrics.py（7 个测试）

| # | 测试名称 | 验证点 |
|---|---------|--------|
| 1 | `test_cost_trend_empty` | 无数据时返回零值默认结构 |
| 2 | `test_cost_trend_with_data` | 插入 ModelCallLog 后 total_cost 正确 |
| 3 | `test_fallback_stats_empty` | 无数据时 fallback_rate = 0 |
| 4 | `test_fallback_stats_with_data` | 降级次数和比率计算正确 |
| 5 | `test_error_stats_with_data` | 错误按类型分组正确 |
| 6 | `test_latency_stats_empty` | 无数据时 avg/p95/p99 = 0 |
| 7 | `test_invalid_period_returns_400` | period=invalid → 400 |

### 8.2 test_admin_corrections_ext.py（8 个测试）

| # | 测试名称 | 验证点 |
|---|---------|--------|
| 1 | `test_correction_detail_ocr` | OCR 类型详情包含 context.original_url |
| 2 | `test_correction_detail_knowledge` | Knowledge 类型详情包含 context.knowledge_point_name |
| 3 | `test_correction_detail_not_found` | 不存在的 ID → 404 |
| 4 | `test_correction_logs_pagination` | 修正历史分页返回正确 |
| 5 | `test_pending_count_by_type` | 按类型统计计数正确 |
| 6 | `test_correct_plan` | 提交计划纠偏创建 pending 记录 |
| 7 | `test_resolve_plan_correction` | resolve 计划纠偏后任务被更新 |
| 8 | `test_resolve_plan_unmatched_tasks` | 不可匹配的任务 → 400 |

### 8.3 test_report_comparison.py（6 个测试）

| # | 测试名称 | 验证点 |
|---|---------|--------|
| 1 | `test_weekly_report_with_previous` | previous_* 字段正确填充 |
| 2 | `test_weekly_report_no_previous` | 上周无数据时 previous_* 为 null |
| 3 | `test_week_boundary_w01` | W01 回退到上一年 W52/W53 正确 |
| 4 | `test_parent_report_support_suggestions` | 家长周报包含 parent_support_suggestions |
| 5 | `test_parent_report_risk_summary` | 家长周报包含 risk_summary |
| 6 | `test_parent_report_avg_daily_minutes` | avg_daily_minutes 计算正确 |

### 8.4 test_security.py（7 个测试）

| # | 测试名称 | 验证点 |
|---|---------|--------|
| 1 | `test_cross_student_plan_access` | 学生 A 不能获取学生 B 的计划 |
| 2 | `test_cross_student_error_access` | 学生 A 不能获取学生 B 的错题 |
| 3 | `test_cross_student_qa_access` | 学生 A 不能获取学生 B 的 QA 会话 |
| 4 | `test_parent_bound_to_student` | 家长只能访问关联学生数据 |
| 5 | `test_forged_jwt_rejected` | 篡改 JWT payload → 401 |
| 6 | `test_expired_share_token` | 过期分享链接 → 错误 |
| 7 | `test_invalid_upload_file_type` | 非图片文件上传 → 400 |

### 8.5 test_smoke.py（1 个测试，覆盖完整流程）

| # | 测试名称 | 验证点 |
|---|---------|--------|
| 1 | `test_full_student_happy_path` | 从登录到周报查看的完整流程 |

---

## 9. 设计决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| E2E 测试工具 | httpx AsyncClient（不引入 Playwright） | MVP 阶段 API 测试足以验证核心闭环；Playwright 引入成本高且需要浏览器环境 |
| CI 平台 | GitHub Actions | 项目已托管在 GitHub；免费额度足够 |
| 生产 Web Server | Nginx + Uvicorn | Nginx 处理 SSL、静态文件、限速；Uvicorn 处理 ASGI 应用 |
| 日志方案 | 标准库 logging + JSON Formatter | 不引入额外依赖（structlog 等）；JSON 格式便于日志平台采集 |
| 容器安全 | 非 root 用户 + 多阶段构建 | 基础安全实践；减小镜像体积和攻击面 |
| 测试覆盖率 | pytest-cov 报告但不设硬性 gate | MVP 阶段关注关键路径覆盖，不追求行覆盖率指标 |

---

## 10. 验证方案

### 10.1 测试验证

```bash
# 后端全量测试
cd server && pytest -x -v --cov=app

# 前端类型检查 + lint
cd web && npx tsc --noEmit && npm run lint

# 后端 lint
cd server && ruff check app/ && ruff format --check app/
```

### 10.2 部署验证

```bash
# 生产 Docker 构建
docker build -f Dockerfile.prod -t studypilot-api:latest .

# Nginx 配置检查
nginx -t -c nginx/nginx.conf

# docker-compose 配置检查
docker compose -f docker-compose.prod.yml config
```

### 10.3 CI 验证

- Push 代码后 GitHub Actions 自动触发
- 3 个 Job 全部绿色

### 10.4 MVP 验收检查清单

基于 PRD §15 和 §16 的验收标准：

- [ ] 至少 3 个科目（语数英/理化）跑通完整主闭环
- [ ] 端到端冒烟测试通过（登录→计划→上传→答疑→错题→周报）
- [ ] 人工纠偏通道可用（OCR/Knowledge/Plan）
- [ ] 家长周报可正常生成和分享
- [ ] 分享链接数据脱敏符合 §13.5 规则
- [ ] 健康检查验证 DB + Redis 连通性
- [ ] CI 流水线 lint + test + build 全部通过
- [ ] 生产 Docker 镜像可构建且启动正常
