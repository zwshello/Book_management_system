# 阶段 7：Vue 前端页面与接口对应

前端使用 Vue 3、TypeScript、Vue Router、Pinia、Axios、Element Plus 与 ECharts。页面采用 Composition API 和 `<script setup lang="ts">`。API 请求集中在 `frontend/src/api/`，类型位于 `frontend/src/types/`。本阶段实现页面和构建，真实浏览器到四服务的完整联调仍属于阶段 8。

| 页面 | 路由 | 权限 | 后端接口 |
| --- | --- | --- | --- |
| 登录 | `/login` | 公开 | `POST /auth/login` |
| 首页 | `/dashboard` | 已登录 | `GET /borrows/me` 摘要及最近记录 |
| 图书查询 | `/books` | 已登录 | `GET /books`、`GET /categories` |
| 图书详情与借书 | `/books/:id` | 已登录 | `GET /books/{id}`、`POST /borrows` |
| 我的借阅与归还 | `/my-borrows` | 已登录 | `GET /borrows/me`、`POST /borrows/{id}/return` |
| 个人信息 | `/profile` | 已登录 | `GET/PATCH /users/me` |
| 管理首页 | `/admin` | ADMIN | `GET /statistics/overview` |
| 用户管理 | `/admin/users` | ADMIN | `GET/POST /users`、`PATCH/DELETE /users/{id}` |
| 图书管理 | `/admin/books` | ADMIN | `GET/POST /books`、`PATCH/DELETE /books/{id}`、`POST /books/{id}/stock-adjustments` |
| 分类管理 | `/admin/categories` | ADMIN | `GET/POST /categories`、`PATCH/DELETE /categories/{id}` |
| 借阅管理 | `/admin/borrows` | ADMIN | `GET /borrows` |
| 统计分析 | `/admin/statistics` | ADMIN | `GET /statistics/overview` |

表中路径省略共同前缀 `/api/v1`。图书查询参数直接采用 book-service 的 `title`、`author`、`isbn`、`category_id`、`status`、`availability`、`page`、`page_size`；管理查询采用各服务已实现参数。图书资料 PATCH 不直接写库存，库存经专用接口调整。

登录响应的 access、refresh 和当前用户资料保存在浏览器 `sessionStorage`。Axios request interceptor 附加 access JWT，收到非登录接口的 401 后清理认证状态并跳转登录页。路由守卫在进入受保护页面前调用 `/users/me` 获取当前账户与角色，普通用户不会进入管理员页面；后端仍为最终权限判断。登出调用 `/auth/logout`，随后清理本地凭据。

借书、归还分别生成 UUID `Idempotency-Key`，在一次请求结果不明或返回待处理状态时将其保留在当前浏览器会话，后续再次提交复用同一编号。收到明确完成或明确 409 冲突后才释放编号。页面提示先查看借阅记录，避免超时后盲目发起新的操作。这个浏览器会话方案不能代替阶段 8 对真实断网、刷新、跨设备行为的联调。

管理员统计卡片和柱状图只使用 statistics-service 已实现的五项概览。普通用户首页使用本人借阅数据，不请求管理员统计。删除/归档用户、图书和分类前使用 Element Plus 二次确认；表单检查非空、长度、邮箱、ISBN 校验位与库存整数，后端继续独立校验。

本地 Vite 开发代理通过 `frontend/.env.example` 中的四个 `VITE_*_SERVICE_TARGET` 指向独立服务。阶段 8 网关接入时，前端 Axios 保持相对 `/api/v1` 路径，由网关统一转发。
