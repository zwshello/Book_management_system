# 当前 REST/JSON API

本页按已实现代码整理。浏览器统一访问 gateway 的 `/api/v1`，例如 `http://127.0.0.1:8080/api/v1/books`；本机端口可由 `GATEWAY_PORT` 改变。公开接口除注册、登录、刷新外使用 `Authorization: Bearer <access JWT>`。路径**不要求末尾斜杠**。请求体和非 204 响应使用 JSON。内部 `/internal/v1/` 不经 gateway 公开。

通用分页响应：`{"count": 2, "page": 1, "page_size": 20, "results": [...]}`。非法字段、重复查询参数和错误格式返回 400；未认证或失效令牌 401；权限不足 403；资源不存在 404；业务冲突 409；必要上游不可用 503。错误体含 `code`、`message`、`details`、`request_id`，响应带 `X-Request-ID`。各状态码以具体接口约束为准。

## user-service

| 方法与 URL | 权限 | 请求参数/JSON | 成功响应 | 常见错误 |
| --- | --- | --- | --- | --- |
| `POST /api/v1/auth/register` | 匿名 | `username`、`email`、`password`，可选 `display_name`；不接受 `role`/`is_active` | 201 用户对象，无密码 | 400 校验或重复 |
| `POST /api/v1/auth/login` | 匿名 | `username`、`password` | 200 `{access,refresh,user}` | 401 凭据错误/账户不可用 |
| `POST /api/v1/auth/refresh` | 持有效 refresh | `{refresh}` | 200 新 access/refresh；角色取当前用户状态 | 401 失效/禁用 |
| `POST /api/v1/auth/logout` | 已登录 | `{refresh}`，必须属于本人 | 204，无响应体 | 400/401 |
| `GET /api/v1/users/me` | 已登录 | 无 | 200 本人用户对象 | 401 |
| `PATCH /api/v1/users/me` | 已登录 | 仅 `email`、`display_name` | 200 更新后的用户对象 | 400/401 |
| `GET /api/v1/users` | 当前管理员 | `username` 精确、`username_contains` 模糊、`role`、`is_active=true/false`、`page`、`page_size`、`ordering` | 200 分页用户列表 | 400/401/403/404 |
| `POST /api/v1/users` | 当前管理员 | `username`、`email`、`password`，可选 `display_name`、`role`、`is_active` | 201 用户对象 | 400/401/403 |
| `GET /api/v1/users/{id}` | 当前管理员 | UUID 路径参数 | 200 用户对象 | 400/401/403/404 |
| `PATCH /api/v1/users/{id}` | 当前管理员 | 上述可修改字段的子集 | 200 更新后的用户对象 | 400/401/403/404/409 |
| `DELETE /api/v1/users/{id}` | 当前管理员 | UUID 路径参数 | 204，**归档并禁用** | 401/403/404/409 |

用户对象主要字段：`id, username, email, display_name, role, is_active, status, created_at, updated_at, archived_at`。`username` 长度 3–150；密码至少 8 字符且受 Django 密码规则约束；用户名和邮箱均按规范化值唯一。用户列表 `ordering` 允许 `username/-username/created_at/-created_at`，默认 `-created_at`。禁止归档、停用或降级最后一名有效管理员。

## book-service

| 方法与 URL | 权限 | 请求参数/JSON | 成功响应 | 常见错误 |
| --- | --- | --- | --- | --- |
| `GET /api/v1/categories` | 已登录 | `name`、`page`、`page_size`、`ordering` | 200 分页分类列表 | 400/401/404 |
| `POST /api/v1/categories` | 当前管理员 | `name`、可选 `description` | 201 分类对象 | 400/401/403 |
| `GET /api/v1/categories/{id}` | 已登录 | UUID | 200 分类对象 | 400/401/404 |
| `PATCH /api/v1/categories/{id}` | 当前管理员 | `name`、`description` 的子集 | 200 分类对象 | 400/401/403/404 |
| `DELETE /api/v1/categories/{id}` | 当前管理员 | UUID | 204，物理删除 | 401/403/404/409（仍被图书引用） |
| `GET /api/v1/books` | 已登录 | `title`/`author` 模糊、`title_exact`/`author_exact` 精确、`isbn`、`category_id`、`status`、`availability`、`page`、`page_size`、`ordering` | 200 分页图书列表 | 400/401/403/404 |
| `POST /api/v1/books` | 当前管理员 | `title`、`author`、`isbn`、`category` UUID，及可选出版信息、`total_copies`、`available_copies`、`status` | 201 图书对象 | 400/401/403 |
| `GET /api/v1/books/{id}` | 已登录 | UUID；普通用户仅能看在架书 | 200 图书对象 | 400/401/403/404 |
| `PATCH /api/v1/books/{id}` | 当前管理员 | 可修改书目资料/状态；**不接受库存字段** | 200 图书对象 | 400/401/403/404/409 |
| `DELETE /api/v1/books/{id}` | 当前管理员 | UUID | 204，**归档**，禁止新预留 | 401/403/404/409 |
| `POST /api/v1/books/{id}/stock-adjustments` | 当前管理员 | `{ "total_copies": 5 }` | 200 更新后的图书对象 | 400/401/403/404/409 |

分类对象：`id, name, description, created_at, updated_at`。图书对象：`id, title, author, isbn, category, category_name, publisher, published_date, description, total_copies, available_copies, status, created_at, updated_at, archived_at`。ISBN-10 输入可转换为规范 ISBN-13，最终唯一；库存不得为负，可借册数不得超过总册数。查询参数按 AND 组合，例如 `GET /api/v1/books?title=Python&category_id=<UUID>&availability=available&page=1&page_size=20&ordering=title`。`availability` 为 `available/unavailable`；排序允许 `title/-title/created_at/-created_at/published_date/-published_date`。`page_size` 为 1–100。普通用户不能查询归档书目；管理员可用 `status=ARCHIVED`。

## borrow-service

借书与还书写请求必须带 `Idempotency-Key: <UUID>`。客户端在超时后应使用**原操作号**核对或重试，不能随意换号。

| 方法与 URL | 权限 | 请求参数/JSON | 成功响应 | 常见错误 |
| --- | --- | --- | --- | --- |
| `POST /api/v1/borrows` | 当前有效用户 | `{ "book_id": "<UUID>" }`，幂等头 | 201 新借阅；200 同号已完成；202 待核对 | 400/401/404/409/503 |
| `GET /api/v1/borrows/me` | 已登录 | `status`、`book_id`、日期范围、分页排序；仅本人 `user_id` | 200 本人分页借阅列表 | 400/401/403/404 |
| `GET /api/v1/borrows` | 当前管理员 | `user_id`、`book_id`、`status`、`created_from`、`created_to`、`include_archived`、分页排序 | 200 全站分页借阅列表 | 400/401/403/404/503 |
| `GET /api/v1/borrows/{id}` | 本人或当前管理员 | UUID | 200 借阅记录 | 400/401/403/404 |
| `POST /api/v1/borrows/{id}/return` | 本人或当前管理员 | 空 JSON `{}`，幂等头 | 200 已归还/重复同号；202 待核对 | 400/401/403/404/409/503 |
| `PATCH /api/v1/borrows/{id}` | 当前管理员 | `{ "due_at": "ISO-8601 时间" }`，仅进行中的记录 | 200 借阅记录 | 400/401/403/404/409 |
| `DELETE /api/v1/borrows/{id}` | 当前管理员 | UUID，仅 `RETURNED/FAILED` | 204，归档历史记录 | 401/403/404/409 |

借阅记录主要字段：`id, user_id, book_id, username_snapshot, book_title_snapshot, isbn_snapshot, status, display_status, is_overdue, borrowed_at, due_at, returned_at, borrow_days, failure_code, last_error_code, created_at, updated_at, archived_at`。持久化状态为 `PENDING/ACTIVE/RETURN_PENDING/RETURNED/FAILED`，`OVERDUE` 是动态显示/筛选状态。`status` 与其他查询条件可组合。日期格式 `YYYY-MM-DD`；分页默认 1/20，上限 100；排序允许 `created_at/-created_at/due_at/-due_at`。

## statistics-service

| 方法与 URL | 权限 | 请求参数 | 成功响应 | 常见错误 |
| --- | --- | --- | --- | --- |
| `GET /api/v1/statistics/overview` | 当前管理员 | 不接受查询参数 | 200 五项统计与 `chart` | 400/401/403/503 |

```json
{
  "user_total": 10,
  "book_total": 8,
  "available_book_titles": 6,
  "available_copies": 21,
  "borrowed_copies": 4,
  "current_borrows": 3,
  "chart": { "labels": ["用户总数", "图书书目数", "可借册数", "已借册数", "当前借阅数"], "values": [10, 8, 21, 4, 3] }
}
```

五项课程统计对应 `user_total`、`book_total`、`available_copies`、`borrowed_copies`、`current_borrows`。`available_book_titles` 是额外提供的辅助字段，不是第六项独立统计功能。可借册数按 ACTIVE 图书库存计；已借册数含 `ACTIVE/RETURN_PENDING`，当前借阅数只计 `ACTIVE`。数据分别来自 user/book/borrow 服务的聚合端点，不能写死或跨库读取。

## 内部服务接口（不对浏览器开放）

| 所有者 | 方法与 URL | 调用方与请求 | 返回 / 状态 |
| --- | --- | --- | --- |
| user-service | `GET /internal/v1/users/{id}/authorization` | book/borrow/statistics 服务凭据 + `X-User-Access-Token` | 当前用户角色和状态；200/401/403/404/503 |
| user-service | `GET /internal/v1/users/{id}/eligibility` | borrow 服务凭据 + 原用户 access | 借阅资格、用户名等；200/401/403/404/503 |
| user-service | `GET /internal/v1/users/summary` | statistics 服务凭据 | `{total_users}`；200/401/503 |
| book-service | `GET /internal/v1/books/summary` | statistics 服务凭据 | 书目、可借标题、可借册数；200/401/503 |
| book-service | `GET /internal/v1/books/{id}/availability` | borrow 服务凭据 | 状态、库存及书目快照；200/401/404/503 |
| book-service | `POST /internal/v1/books/{id}/reservations` | borrow 服务凭据，`{borrow_id}` + 幂等头 | 原子预留一册及操作结果；200/400/401/404/409/503 |
| book-service | `POST /internal/v1/books/{id}/releases` | borrow 服务凭据，`{borrow_id}` + 幂等头 | 释放一册及操作结果；200/400/401/404/409/503 |
| book-service | `GET /internal/v1/books/operations/{operation_key}` | borrow 服务凭据 | 先前库存操作结果；200/401/404/503 |
| borrow-service | `GET /internal/v1/borrows/summary` | statistics 服务凭据 | `{borrowed_copies,current_borrows}`；200/401/503 |

内部调用 URL 来自服务环境变量；服务身份凭据与用户 JWT 分离。各端点具体字段及异常语义见 [阶段 3–6 接口文档](phase-3/user-service-api.md)、[借还流程](phase-5/workflow.md)。
