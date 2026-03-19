# 前端已知问题 (Known Issues)

> 代码审查发现的问题清单。已修复的标记为 ~~删除线~~，未修复的按优先级排列。

## 已修复

- ~~**QA 流式响应内存泄漏** (`qa/page.tsx`) — streaming 循环无 abort 机制，组件卸载后仍执行 setState~~
- ~~**QA sendMessage 逻辑 bug** (`qa/page.tsx`) — `!input.trim() && !sending` 应为 `||`，sending=true 时可发空消息~~
- ~~**QA setSending 无 finally 清理** (`qa/page.tsx`) — 异常时 sending 状态永远卡在 true~~
- ~~**Blob URL 内存泄漏** (`upload/page.tsx`) — createObjectURL 后从未 revokeObjectURL~~
- ~~**OCR 状态文字 class 错误** (`upload/page.tsx`) — `.replace("text-", "text-white")` 生成无效类名如 `text-whiteprimary`~~
- ~~**Onboarding 草稿恢复竞态** (`onboarding/page.tsx`) — React Strict Mode 下 save effect 可能用默认值覆盖已保存草稿~~
- ~~**Onboarding 考试列表用 index 作 key** (`onboarding/page.tsx`) — 删除中间项时 DOM 复用错误~~
- ~~**usePathname 未使用** (`app-header.tsx`) — 多余导入导致不必要的路由订阅~~
- ~~**日期格式化无效输入** (`utils.ts`) — formatDate/formatTime/getWeekday 对无效日期输出 NaN~~
- ~~**Dashboard 周汇总硬编码** (`dashboard/page.tsx`) — 数字固定写死未从 mock 数据取值~~

## 未修复 — 需要架构层面变更

### P0: 路由保护缺失

**影响**: 所有已认证页面和管理后台页面无任何 auth guard，直接访问 URL 可绕过登录。

**涉及文件**: 所有 `src/app/` 下的页面路由

**建议方案**:
1. 创建 `src/middleware.ts`（Next.js middleware），拦截所有非公开路由
2. 检查 cookie/token，未认证重定向到 `/login`
3. 管理员路由 (`/admin/*`) 额外检查 `user_role === "admin"`
4. 家长路由 (`/parent/*`) 检查 `user_role === "parent"`

**为何未修复**: 需要与后端 auth 方案（JWT/session）一并设计，单独在前端做 localStorage 检查仅是权宜之计，后端对接时必须替换。建议在 Phase 4（前后端联调）时统一实现。

### P1: Share 页面 token 未使用

**影响**: `share/[token]/page.tsx` 中 `params.token` 从未读取，过期逻辑 (`expired` state) 是不可达的死代码。任意 token URL 均显示相同 mock 数据。

**涉及文件**: `src/app/share/[token]/page.tsx`

**建议方案**:
1. 后端实现 `GET /api/v1/share/{token}` 接口
2. 前端用 token 调用 API，处理 404（无效）和 410（已过期）响应
3. 设置 `expired` 状态触发过期 UI

**为何未修复**: 该页面的核心逻辑依赖后端 share token 验证接口，纯前端修复无意义。

### P1: Onboarding 草稿保存不完整

**影响**: `onboarding/page.tsx` 的 auto-save 未保存排名字段（classRank, gradeRank 等），刷新后丢失。`onboarding_completed` flag 无用户 ID 作用域，共享设备上会跳过其他用户的 onboarding。

**涉及文件**: `src/app/onboarding/page.tsx`

**建议方案**:
1. 将排名字段加入 draft save/restore
2. `onboarding_completed` key 加入 user_id 前缀，如 `onboarding_completed_{userId}`
3. 后端对接后改用服务端 onboarding 状态

**为何未修复**: 排名字段为可选数据，丢失影响低；用户 ID 作用域在单用户 MVP 阶段不是问题，但需在多用户测试前修复。

### P2: cn() 工具缺少 tailwind-merge

**影响**: `utils.ts` 中 `cn()` 仅做简单字符串拼接，无法解决 Tailwind class 冲突（如 `text-primary` 和 `text-white` 同时存在时行为不可预测）。

**涉及文件**: `src/lib/utils.ts`，以及所有使用 `cn()` 传递覆盖 className 的组件

**建议方案**:
```bash
npm install clsx tailwind-merge
```
```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

**为何未修复**: 当前实际冲突场景有限（已修复了 upload 页面的主要冲突），引入新依赖需评估 bundle size 影响。建议在下一次依赖升级时一并处理。

### P2: Toast setTimeout 未清理

**影响**: `toast.tsx` 中 `setTimeout` 返回值未存储，ToastProvider 卸载时无法取消。实际风险极低（Provider 在 root layout 几乎不会卸载）。

**涉及文件**: `src/components/ui/toast.tsx`

**建议方案**: 使用 `useRef` 存储 timer ID，在 cleanup 中 `clearTimeout`。

**为何未修复**: 实际影响几乎为零，属于防御性编程改进。

### P2: 周报/家长报告 suggestions 列表用 index 作 key

**影响**: `report/weekly/page.tsx`、`parent/report/weekly/page.tsx`、`share/[token]/page.tsx` 中 suggestions 数组用 `key={i}`。

**涉及文件**: 3 个报告页面

**为何未修复**: suggestions 是只读的服务端数据，不会在客户端增删排序，index 作 key 不会引起实际问题。
