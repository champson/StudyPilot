# AI高考伴学教练

面向上海高中学生的个性化 AI 辅学系统。产品围绕学校教学节奏运行，通过每日计划、内容上传、实时答疑、错题沉淀与召回、周报反馈，帮助学生在有限课后时间内完成查缺补漏和阶段提分。

当前仓库已经包含一套可运行的 MVP 工程实现：

- `server/`：FastAPI API、Celery worker / beat、Alembic 迁移、PostgreSQL / Redis 接入
- `web/`：Next.js App Router 前端
- `docs/`：PRD、接口契约、阶段设计与复查文档

第一阶段目标仍然是跑通小范围真实学生的 MVP 闭环，而不是先做一个大而全的平台。

## 项目目标

- 跟随学生日常校内学习节奏，生成当天可执行的学习计划
- 在有限课后时间内，推荐最值得优先投入的 2-3 门重点学科
- 在学生卡题时提供结构化答疑，并把答疑结果沉淀为后续学情数据
- 自动归档错题并在后续再次召回，形成持续补弱闭环
- 在周报和阶段报告中向学生与家长展示趋势、风险和建议

## 目标用户

- 学生：主操作角色，负责上传内容、执行计划、做题和发起答疑
- 家长：查看周报、阶段报告，必要时补录成绩或基础信息
- 人工支持方：仅在系统失败场景下介入，负责 OCR 失败、计划纠偏、答疑纠偏等兜底处理

首期使用范围控制在 5 人以内，以熟悉学生的小规模试运行验证产品闭环。

## 产品定位

这不是一个通用聊天机器人，也不是一个完整题库平台。系统更像一个围绕学校学习节奏工作的课后 AI 学习工作台，强调：

- 先给行动建议，再给知识解释
- 先服务学生执行，再服务家长感知
- 先形成闭环，再扩展功能
- 优先可解释推荐，不追求黑盒最优

## 学科与时间范围

- 产品能力设计支持 9 门学科：语文、数学、英语、物理、化学、地理、政治、生物、历史
- 首期 MVP 验收以 5 门学科为准：语文、数学、英语、物理、化学
- 每日学习计划不平均铺开全部学科，而是根据学生当前场景与可用时间，推荐 2-3 门重点学科
- 学生单次可用时长通常为 45-90 分钟，系统需在该约束下输出清晰、可执行的任务流

## MVP 范围

MVP 围绕一个学生学习工作台和五个核心模块展开：

1. 今日计划
2. 上传入口
3. 实时答疑
4. 错题本（含再次召回）
5. 周报 / 趋势

首期不做：

- 完整家长独立端
- 社交、社区、排行榜
- 开放式闲聊
- 大规模题库运营后台
- 高三专属复杂冲刺模式

## 核心流程

### 1. 首次建档

学生或家长补录基础信息：

- 年级
- 教材版本
- 学科组合
- 班级排名 / 年级排名
- 近期考试节点
- 历次考试记录

### 2. 每日学习

标准主流程如下：

1. 学生进入工作台
2. 选择或确认当前学习模式：工作日跟学、周末复习
3. 确认本次可用学习时间
4. 上传当天学校内容、作业、讲义、试卷或成绩
5. 系统识别学科、知识点和近期学习上下文
6. 系统推荐 2-3 门重点学科和流程卡片任务
7. 学生逐步完成任务，并在过程中随时发起答疑
8. 错题自动沉淀，后续再次召回
9. 数据进入周报和阶段报告

### 3. 周末复习

周末模式不依赖当天学校新学内容，而是优先使用：

- 本周错题
- 历史薄弱点
- 再次召回记录
- 近期考试表现

## 核心模块说明

### 今日计划

负责根据学习模式、可用时间、学校进度、历史成绩、错题情况和考试临近度，生成当日优先级和流程卡片。

### 上传入口

负责以最低成本把学校学习内容带入系统，支持：

- 拍照上传
- 语音输入
- 文本输入
- 学生手填
- 家长补录

其中拍照上传是主输入方式。

### 实时答疑

学生在任何任务节点都可以发起提问。系统需要识别题目难度和知识点，并给出讲解、提示、追问或完整步骤说明。答疑后必须有下一步动作，而不是只停留在解释。

### 错题本

将“做错、不会、反复错”的题自动沉淀为可复用学习资产，并支持后续再次召回。错题状态变化将持续影响掌握度和后续推荐。

### 周报 / 趋势

为学生和家长输出统一的结构化反馈，包括：

- 使用频率与使用时长
- 重点学科表现变化
- 高风险知识点
- 阶段成绩变化
- 下阶段建议

## MVP 验收重点

- 学生可在工作台完成从上传到计划生成的完整流程
- 学生可在任务中随时发起答疑
- 错题可自动入库并支持再次召回
- 周报和阶段报告可正常生成并分享
- 语文、数学、英语、物理、化学至少三门完整闭环可跑通，其余两门具备基础能力

## 项目边界

- 不替代学校授课和老师批改
- 不在首期构建完整课程体系或通用题库平台
- 不把产品做成开放式泛聊天工具
- 不在首期处理复杂商业化、社交裂变或 B 端交付需求

## 异常与兜底

首期允许以人工兜底换取验证速度，人工支持方主要在以下失败场景介入：

- OCR 失败
- 计划明显不合理
- 答疑质量差
- 知识点标注错误

系统默认原则是不中断主流程，优先给出保守型可执行方案，再允许后续人工纠偏。

## 里程碑

### 里程碑一：基础闭环可跑通

- 完成学生建档
- 完成学习工作台
- 打通上传、计划、答疑、错题沉淀主链路

### 里程碑二：小规模试运行

- 覆盖 5 人以内真实学生
- 形成稳定周报输出
- 跑通人工纠偏机制

### 里程碑三：阶段效果验证

- 跟踪月考或期中考试变化
- 验证重点学科提升和排名变化

## 仓库文档

- PRD 主文档：[docs/prd.md](docs/prd.md)

后续建议继续补齐：

- 页面级 PRD
- 推荐与答疑策略文档
- 技术架构设计
- 接口与数据模型设计

## 工程结构

```text
.
├── server/                 # FastAPI 后端
│   ├── app/                # API / services / models / tasks
│   ├── alembic/            # 数据库迁移
│   ├── tests/              # 后端测试
│   ├── docker-compose.yml  # 本地后端一键依赖
│   └── docker-compose.prod.yml
├── web/                    # Next.js 前端
└── docs/                   # 产品与技术文档
```

## 本地运行

### 1. 前置依赖

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- Redis 7+

### 2. 配置环境变量

后端：

```bash
cd server
cp .env.example .env
```

前端：

```bash
cd web
cp .env.example .env.local
```

默认前端变量：

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1
```

### 3. 启动后端

```bash
cd server
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

如需异步 OCR / 周报任务，再启动 worker 和 beat：

```bash
cd server
celery -A app.tasks.celery_app:celery worker -l info
celery -A app.tasks.celery_app:celery beat -l info
```

### 4. 启动前端

```bash
cd web
npm install
npm run dev
```

默认访问：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`

## 使用 Docker 启动后端依赖

如果你本地有 Docker，可以直接启动 PostgreSQL、Redis、API、worker、beat：

```bash
cd server
docker compose up --build
```

说明：

- 该 compose 只覆盖后端栈，不包含 `web/`
- API 会读取 [server/.env.example](server/.env.example) 中的默认配置
- 容器内数据库地址是 `db:5432`，宿主机直连地址是 `localhost:5432`

## 生产部署

当前仓库推荐“前后端分离”部署：

- 后端：Docker Compose / VM / 容器平台
- 前端：Vercel、Node 进程、或任意支持 Next.js `build + start` 的平台

### 后端生产部署

1. 准备生产环境变量：

```bash
cd server
cp .env.example .env
```

至少修改这些值：

- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET_KEY`
- `SHARE_TOKEN_SECRET`
- `ADMIN_PASSWORD`
- `DEBUG=false`

2. 启动生产 compose：

```bash
cd server
docker compose -f docker-compose.prod.yml up -d --build
```

说明：

- `api` 容器启动时会自动执行 `alembic upgrade head`
- `worker` 负责 OCR、周报等异步任务
- `beat` 负责定时任务调度
- `nginx` 负责 `/api/*` 反向代理与 `/uploads/*` 静态文件分发

建议上线前确认：

- `DB_PASSWORD` 已设置为强密码
- `JWT_SECRET_KEY` / `SHARE_TOKEN_SECRET` 不再使用默认值
- `uploads` 卷路径有备份策略
- `HTTP_PORT`、`API_WORKERS`、`LOG_LEVEL` 已按机器规格调整

### 前端生产部署

最小要求：

```bash
cd web
npm install
npm run build
NEXT_PUBLIC_API_BASE=https://your-api-domain/api/v1 npm run start
```

部署时必须设置：

- `NEXT_PUBLIC_API_BASE`

建议把它指向生产 API 域名，例如：

```bash
NEXT_PUBLIC_API_BASE=https://api.example.com/api/v1
```

如果前端与后端分开部署，请同时确认：

- 后端 `CORS_ORIGINS` 允许前端域名
- Nginx / 反向代理对 SSE 路径 `/api/v1/student/qa/chat/stream` 关闭缓冲
- 分享页 `/share/[token]` 能访问到同一套后端 API

## 验证命令

后端：

```bash
cd server
pytest -q
ruff check .
```

前端：

```bash
cd web
npm run lint
npm run build
```

## 当前状态

当前仓库已经具备 MVP 工程骨架与主要主链路实现，重点工作转向：

- 持续对齐产品设计、接口契约与代码实现
- 用小规模真实学生验证上传 → 计划 → 答疑 → 错题 → 周报闭环
- 在不打断主流程的前提下完善人工纠偏与异步任务稳定性

技术实现可以采用多 Agent、大模型、OCR、外部题目能力和人工兜底的组合，但这些是实现方案，不是产品需求本身。
