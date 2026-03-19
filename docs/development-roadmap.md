# AI高考伴学教练 — 开发路线图

> 基于已完成的前端页面（Next.js + TailwindCSS + Mock 数据）和设计文档，规划后续开发步骤。

## 当前状态

| 层级 | 状态 | 说明 |
|------|------|------|
| 产品设计文档 | ✅ 已完成 | PRD、页面级 PRD、架构设计、API 契约、ER 图、权限矩阵 |
| 前端页面 | ✅ 已完成 | 14 个路由全部可编译，使用 Mock 数据，响应式适配 |
| 后端服务 | ❌ 未开始 | FastAPI + PostgreSQL + Redis + Celery |
| LLM Agent | ❌ 未开始 | LangGraph 编排，模型路由 |
| 部署基础设施 | ❌ 未开始 | 阿里云 ECS / OSS / RDS |

---

## Phase 1: 后端基础搭建

### 1.1 项目脚手架

目标：建立 `/server/` 后端项目，可本地启动。

- FastAPI 项目初始化（Python 3.11+, Pydantic V2）
- 目录结构规划：
  ```
  server/
  ├── app/
  │   ├── api/v1/          # 路由层
  │   ├── models/          # SQLAlchemy ORM models
  │   ├── schemas/         # Pydantic request/response schemas
  │   ├── services/        # 业务逻辑层
  │   ├── core/            # 配置、安全、依赖注入
  │   └── tasks/           # Celery 异步任务
  ├── alembic/             # 数据库迁移
  ├── tests/
  ├── requirements.txt
  └── Dockerfile
  ```
- 配置管理：dev / staging / prod 环境变量（`.env` 文件）
- Docker Compose 编排：PostgreSQL 15 + Redis 7 + FastAPI + Celery Worker

依赖文档：`docs/architecture_design.md`

### 1.T 测试计划

| 测试类型 | 范围 | 工具 | 通过标准 |
|----------|------|------|----------|
| 冒烟测试 | Docker Compose 一键启动 | `docker compose up` | 所有容器健康，FastAPI `/health` 返回 200 |
| 数据库迁移测试 | Alembic upgrade / downgrade | pytest + alembic | `upgrade head` 和 `downgrade base` 可往返执行无报错 |
| 认证单元测试 | JWT 签发、验证、过期、刷新 | pytest | 覆盖：正常签发、过期拒绝、角色校验、刷新续签 |
| 权限中间件测试 | 角色越权拦截 | pytest + httpx | 学生不能访问 admin 接口；家长不能访问学生写入接口；未登录返回 401 |
| ORM 模型测试 | 所有 model CRUD | pytest + 真实 PostgreSQL（测试容器） | 每张表可 create / read / update / delete，外键约束生效 |

### 1.2 数据库层

- 基于 `docs/er-diagram.md` 用 SQLAlchemy 2.0（async）定义所有 ORM models
- 初始化 Alembic 迁移系统
- 核心表（按优先级）：
  - `students` — 学生档案
  - `student_profiles` — 学习偏好（年级、教材、科目）
  - `daily_plans` / `plan_tasks` — 每日计划与任务
  - `uploads` — 上传记录
  - `qa_sessions` / `qa_messages` — 答疑会话与消息
  - `error_book_items` — 错题本
  - `knowledge_points` / `knowledge_mastery` — 知识点与掌握状态
  - `weekly_reports` — 周报
  - `corrections` — 人工纠偏记录
  - `system_metrics` — 系统监控快照

依赖文档：`docs/er-diagram.md`, `docs/api-contract.md`

### 1.3 认证模块

- JWT 签发 / 验证 / 刷新
- 三种登录方式：
  - 学生：邀请 Token 登录
  - 家长：关联 Token 登录
  - 管理员：用户名 + 密码登录
- 角色权限中间件（基于 `docs/page-field-permission-matrix.md`）
- 接口：
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/refresh`
  - `GET /api/v1/auth/me`

依赖文档：`docs/page-field-permission-matrix.md`, `docs/api-contract.md`

---

## Phase 2: 核心 P0 API 实现

按照 `docs/api-contract.md` 和 `docs/api-openapi.yaml` 逐模块实现。

### 2.1 今日计划模块

- `GET /api/v1/plans/today` — 获取或生成今日计划
- `PATCH /api/v1/plans/tasks/{id}/status` — 更新任务状态
- 任务状态流转：`pending → entered → executed → completed`
- 计划生成逻辑：
  1. 判断当前学习模式（工作日跟学 / 周末复习 / 考试冲刺）
  2. 模式优先，在模式内按科目风险度 + 知识点掌握度排序
  3. 选择 1-3 个科目，每科分配具体任务
  4. 计划来源标记：`upload_corrected` / `history_inferred` / `manual_adjusted` / `generic_fallback`

### 2.2 上传入口模块

- `POST /api/v1/uploads` — 文件上传（FormData，支持图片 / 文本）
- `GET /api/v1/uploads` — 上传历史列表
- OCR 异步处理（Celery task）：
  1. 接收上传 → 返回 `processing` 状态
  2. 后台执行 OCR 识别 → 结构化提取
  3. 更新状态为 `completed` 或 `failed`
- 阿里云 OSS 对象存储集成

### 2.3 实时答疑模块

- `POST /api/v1/qa/sessions` — 创建答疑会话
- `POST /api/v1/qa/sessions/{id}/messages` — 发送学生消息
- `GET /api/v1/qa/sessions/{id}/messages/stream` — SSE 流式响应
- `GET /api/v1/qa/sessions` — 历史会话列表
- 答疑策略：结构化回答 + 追问引导 + 知识点标注 + 下一步建议

### 2.4 错题本模块

- `GET /api/v1/errors` — 错题列表（支持科目筛选、状态筛选、关键词搜索）
- `PATCH /api/v1/errors/{id}` — 更新错题状态 / 标记已掌握
- `GET /api/v1/errors/summary` — 各科目错题统计
- 自动归档：从答疑会话和上传内容中自动提取错题

### 2.T 测试计划

| 测试类型 | 范围 | 工具 | 通过标准 |
|----------|------|------|----------|
| 今日计划单元测试 | 计划生成逻辑 | pytest | 工作日模式生成 1-3 科目；周末模式优先错题复习；无上传时降级到 `generic_fallback` |
| 任务状态流转测试 | 状态机合法性 | pytest | 只能按 `pending→entered→executed→completed` 顺序推进；非法跳转返回 400 |
| 上传接口测试 | 文件上传 + OCR 异步 | pytest + httpx + Celery eager 模式 | 图片上传返回 `processing`；OCR 完成后状态更新为 `completed`；超大文件被拒绝 |
| 答疑接口测试 | 会话创建、消息发送 | pytest + httpx | 创建会话返回 session_id；消息保存到 DB；SSE 端点可连接并返回流数据 |
| 错题本接口测试 | CRUD + 筛选 | pytest + httpx | 科目筛选、状态筛选、关键词搜索结果正确；summary 统计数与实际一致 |
| API 契约一致性测试 | 响应格式 vs `api-openapi.yaml` | schemathesis 或 pytest | 所有接口响应符合 OpenAPI schema 定义；字段类型、必填项一致 |
| 并发安全测试 | 同一任务并发状态更新 | pytest + asyncio | 并发更新同一 task 不产生脏数据；乐观锁或数据库约束生效 |

---

## Phase 3: LLM Agent 集成

### 3.1 LangGraph Agent 编排

- **计划生成 Agent**
  - 输入：学生档案 + 当前模式 + 知识点掌握状态 + 科目风险度
  - 输出：结构化每日计划（科目、任务列表、优先级、来源标记）
  - 两层状态模型：知识点掌握度（5 级）× 科目风险度（4 级）

- **答疑 Agent**
  - 输入：学生问题 + 上下文（科目、知识点、历史对话）
  - 输出：结构化回答 + 追问引导 + 关联知识点 + 下一步建议
  - 支持多轮对话，流式输出

- **错题分析 Agent**
  - 输入：错题内容 + 学生作答
  - 输出：错因归类 + 关联知识点 + 相似题推荐

### 3.2 模型路由与成本控制

- 正常效果模式：国产 LLM（DeepSeek / Qwen），月成本约 ¥1,200（5 学生）
- 最优效果模式：GPT-4o / Claude，月成本约 ¥3,700（5 学生）
- 管理后台可切换系统运行模式
- 成本实时监控 + 月度预算告警

### 3.3 OCR Pipeline

- 图片预处理（旋转校正、降噪、增强对比度）
- OCR 识别（阿里云 OCR / 百度 OCR）
- 手写体识别优化
- 结构化内容提取（题目、选项、答案分段）
- 失败降级策略：OCR 失败 → 自动创建人工纠偏工单

### 3.T 测试计划

| 测试类型 | 范围 | 工具 | 通过标准 |
|----------|------|------|----------|
| 计划 Agent 单元测试 | 输入→输出结构 | pytest + LLM mock | 给定固定学生档案和掌握状态，输出符合 schema 的结构化计划；科目数 ≤3；来源标记正确 |
| 答疑 Agent 单元测试 | 多轮对话 + 知识点标注 | pytest + LLM mock | 回答包含 `knowledge_points` 字段；追问引导不为空；流式输出 chunk 格式正确 |
| 错题分析 Agent 测试 | 错因归类准确性 | pytest + 人工标注样本 | 对 20 道标注样本，错因分类准确率 ≥ 80% |
| OCR Pipeline 测试 | 印刷体 / 手写体识别 | pytest + 测试图片集 | 印刷体识别率 ≥ 95%；手写体识别率 ≥ 85%；失败时自动创建纠偏工单 |
| 模型路由测试 | 模式切换 + 降级 | pytest | 正常模式调用国产 LLM；最优模式调用 GPT-4o/Claude；API key 失效时自动降级 |
| 成本计量测试 | Token 用量统计 | pytest + LLM mock | 每次调用记录 input/output token 数；费用计算与模型单价一致 |
| Agent 超时/异常测试 | LLM 超时、返回格式错误 | pytest + mock 异常 | LLM 超时 30s 后返回友好错误；JSON 解析失败时触发重试（最多 2 次） |

---

## Phase 4: 前后端联调

### 4.1 Mock → Real API 切换

逐页面将 `mock-data.ts` 调用替换为 `api.ts` 真实请求：

1. `/login` — 对接认证 API
2. `/onboarding` — 对接学生档案创建 API
3. `/dashboard` — 对接计划摘要 + 统计 API
4. `/plan/today` — 对接今日计划 API + 状态更新
5. `/upload` — 对接文件上传 API + OCR 状态
6. `/qa` — 对接答疑 API + SSE 流式
7. `/errors` — 对接错题本 API

### 4.2 实时功能接入

- QA 页面：SSE 流式响应对接（`EventSource`）
- Upload 页面：OCR 处理状态轮询或 WebSocket 通知
- Plan 页面：任务状态实时同步

### 4.3 错误处理完善

- 网络异常 → Toast 提示 + 可选重试
- 401 Unauthorized → 自动跳转 `/login`
- 业务错误码 → 用户友好中文提示（基于 `api-contract.md` 错误码表）
- 请求 loading 状态 → 替换当前 `setTimeout` 模拟

### 4.T 测试计划

| 测试类型 | 范围 | 工具 | 通过标准 |
|----------|------|------|----------|
| 页面冒烟测试 | 14 个路由可访问 | Playwright / Cypress | 所有页面加载无白屏、无控制台 JS 错误 |
| 登录流程 E2E | 三种角色登录→跳转 | Playwright | 学生登录→`/dashboard`；家长登录→`/parent/report/weekly`；管理员登录→`/admin/dashboard` |
| 今日计划 E2E | 加载→状态更新→进度 | Playwright | 计划加载展示任务列表；点击任务状态按钮后 UI 更新；进度条数值正确 |
| 上传流程 E2E | 选择文件→上传→OCR 状态 | Playwright | 图片预览正常；上传后显示 processing；OCR 完成后状态更新 |
| 答疑流程 E2E | 发送消息→流式响应 | Playwright | 消息发送后出现在对话列表；AI 回复逐字流式展示；知识点标签可见 |
| SSE 连接测试 | 流式中断与重连 | 手动 + Playwright | 网络断开后提示用户；恢复后自动重连；消息不丢失 |
| 响应式布局测试 | 移动端（375px）+ 桌面端（1440px） | Playwright 多视口 | 所有页面在两种视口下布局正常，无溢出、无遮挡 |
| 错误处理测试 | 网络断开、401、500 | Playwright + 网络拦截 | 网络异常显示 Toast；401 跳转登录页；500 显示友好错误信息 |

---

## Phase 5: 辅助功能

### 5.1 周报模块

- `GET /api/v1/reports/weekly` — 学生周报
- `GET /api/v1/reports/weekly/parent` — 家长周报（脱敏版，无排名、无原始图片）
- Celery 定时任务：每周一自动生成上周周报
- 周报内容：使用天数、总时长、完成率、各科目表现、风险点、建议

### 5.2 分享链接

- `POST /api/v1/share` — 生成分享 Token（7 天有效期）
- `GET /api/v1/share/{token}` — 公开访问，仅返回摘要数据
- 数据脱敏：不包含原始题目图片、完整答疑记录、排名信息

### 5.3 管理后台 API

- `GET /api/v1/admin/metrics` — 系统监控（活跃用户、LLM 调用、费用、错误率、OCR 成功率）
- `GET /api/v1/admin/corrections` — 纠偏队列列表
- `PATCH /api/v1/admin/corrections/{id}` — 处理 / 忽略纠偏
- `POST /api/v1/admin/mode` — 切换系统运行模式（正常效果 / 最优效果）

### 5.T 测试计划

| 测试类型 | 范围 | 工具 | 通过标准 |
|----------|------|------|----------|
| 周报生成测试 | 定时任务触发 + 内容正确性 | pytest + Celery eager | 周一触发后生成上周周报；使用天数、总时长、完成率计算正确 |
| 家长周报脱敏测试 | 敏感字段过滤 | pytest | 家长周报不包含：原始题目图片路径、完整答疑记录、排名数据 |
| 分享链接测试 | 生成 + 过期 + 脱敏 | pytest + httpx | Token 7 天内可访问；过期返回 410；响应不包含敏感字段 |
| 管理后台权限测试 | 非 admin 角色拒绝 | pytest + httpx | 学生/家长访问 admin 接口返回 403 |
| 纠偏流程测试 | 创建→处理→忽略 | pytest | OCR 失败自动创建纠偏；管理员标记已处理后状态更新；忽略操作记录原因 |
| 监控数据准确性测试 | metrics 聚合统计 | pytest | LLM 调用次数、费用、错误率与实际记录一致；OCR 成功率计算正确 |

---

## Phase 6: 测试与部署

### 6.1 全量回归测试 & 性能测试

**回归测试（上线前 Gate）：**

| 测试类型 | 范围 | 工具 | 通过标准 |
|----------|------|------|----------|
| 后端全量单元测试 | 所有 service / model | pytest | 通过率 100%，行覆盖率 ≥ 80% |
| API 集成测试 | 所有 API 端点 | pytest + httpx + 测试数据库 | 全部通过，响应符合 OpenAPI schema |
| 前端 E2E 回归 | 核心用户流程（5 条 happy path） | Playwright | 登录→计划→上传→答疑→错题全流程通过 |
| 数据库迁移回归 | upgrade + downgrade 全链路 | alembic | 从空库 `upgrade head` 成功；`downgrade base` 后再 `upgrade head` 无报错 |

**性能测试：**

| 测试类型 | 场景 | 工具 | 通过标准 |
|----------|------|------|----------|
| API 响应时间 | 5 并发用户常规操作 | locust / k6 | P95 响应时间 ≤ 500ms（不含 LLM 调用） |
| LLM 响应时间 | 答疑首字延迟 | 自定义脚本 | 首字输出 ≤ 3s（正常模式）；≤ 5s（最优模式） |
| 文件上传 | 5MB 图片上传 | k6 | 上传成功率 100%；响应 ≤ 2s |
| 数据库查询 | 错题本分页查询（1000 条数据量） | pytest + EXPLAIN ANALYZE | 查询耗时 ≤ 50ms；无全表扫描 |
| SSE 长连接 | 5 并发 SSE 连接，持续 5 分钟 | 自定义脚本 | 无断连；内存无泄漏 |

**安全测试：**

| 测试类型 | 范围 | 工具 | 通过标准 |
|----------|------|------|----------|
| 越权访问 | 学生 A 访问学生 B 数据 | pytest | 全部返回 403 |
| SQL 注入 | 搜索、筛选参数 | sqlmap / 手动 | 无注入漏洞 |
| JWT 安全 | 伪造 / 篡改 / 过期 token | pytest | 伪造 token 返回 401；篡改 payload 返回 401 |
| 文件上传安全 | 恶意文件类型 | pytest | 仅允许 jpg/png/webp；其他类型返回 400 |
| 分享链接隔离 | 分享页不泄露内部 API | 手动审查 | 分享页仅调用公开 GET 接口，无 JWT 暴露 |

### 6.2 基础设施部署

- 阿里云资源：
  - ECS 或容器服务（FastAPI + Celery）
  - RDS PostgreSQL 15
  - Redis 实例
  - OSS Bucket（学生上传文件）
- Nginx 反向代理 + HTTPS 证书
- 前端 Vercel 部署或 OSS 静态托管

### 6.3 MVP 验证（≤5 学生）

验收标准（来自 PRD）：
- [ ] 至少 3 个科目具备完整工作流（上传 → 计划 → 答疑 → 错题 → 周报）
- [ ] 至少 2 个科目功能可用
- [ ] 端到端流程可跑通
- [ ] 月度 LLM 成本在预算范围内（正常模式 ≤ ¥1,200）
- [ ] 人工纠偏通道可用（OCR 失败、计划纠偏、答疑纠偏）
- [ ] 家长周报可正常生成和分享
- [ ] 分享链接数据脱敏符合规则

---

## 开发优先级总览

```
Phase 1 ──→ Phase 2 ──→ Phase 4
  后端基础     P0 API      前后端联调
                ↕              ↓
            Phase 3        Phase 5
            LLM Agent      辅助功能
                               ↓
                           Phase 6
                           测试与部署
```

- Phase 1 → 2 串行：先有基础设施才能写业务
- Phase 2 ↔ 3 可并行：API 层和 Agent 层可独立开发，最后集成
- Phase 4 依赖 Phase 2 完成
- Phase 5 在核心功能稳定后推进
- Phase 6 在功能完整后进行
