# 阶段 5：borrow-service API

本地地址 `http://127.0.0.1:8003`，路径无尾斜杠。公开请求使用 `Authorization: Bearer <user access>`，请求与响应为 JSON。`Idempotency-Key` 为客户端生成的 UUID，借书、归还必须提供。借阅记录只保存 user_id、book_id 和少量展示快照，不访问其他服务的数据库。

## 借阅规则与状态

借期默认 30 天，每人同时最多 5 本，二者可由 BORROW_DAYS、MAX_ACTIVE_BORROWS 配置；这是用户在阶段 5 确认的规则。逾期不自动罚款，仍允许本人或管理员归还。PENDING、ACTIVE、RETURN_PENDING 计入 5 本上限；RETURNED、FAILED 不计。`OVERDUE` 是 ACTIVE 且 due_at 已过的派生显示状态，并非数据库状态；普通用户仍可归还。

数据库状态沿用阶段 1：PENDING → ACTIVE → RETURN_PENDING → RETURNED；明确失败从 PENDING → FAILED。库存操作结果不明时停留在 PENDING 或 RETURN_PENDING，API 返回 202；不能把超时当成库存失败或成功。

## 公开接口

| 方法与路径 | 权限 | 行为 |
| --- | --- | --- |
| POST /api/v1/borrows | 当前有效用户 | JSON `{"book_id":"UUID"}`；首次完成 201、相同编号已完成 200、待核对 202；图书不存在 404、不可借/上限/库存不足 409 |
| GET /api/v1/borrows/me | 已登录 | 只查本人非归档记录，支持状态、图书、日期、分页 |
| GET /api/v1/borrows | 当前管理员 | 查全部；支持 user_id、book_id、status、日期范围、分页与排序 |
| GET /api/v1/borrows/{id} | 本人或当前管理员 | 资料及处理状态；其他用户 403；管理员可审计归档记录 |
| POST /api/v1/borrows/{id}/return | 本人或当前管理员 | 空 JSON 对象及新 Idempotency-Key；成功 200、结果不明 202、非法状态/编号 409；已归还再调用返回既有结果 |
| PATCH /api/v1/borrows/{id} | 当前管理员 | 只接受 `due_at`，只允许未归档 ACTIVE 且晚于 borrowed_at |
| DELETE /api/v1/borrows/{id} | 当前管理员 | 只归档 RETURNED/FAILED；204，不删除历史行 |

普通用户的 `/me` 和本人详情按 JWT sub 限定；管理查询、改期、归档、代还均通过 user-service 实时核验当前角色与状态。用户 JWT 初步验证使用 user-service 的 RS256 公钥，不复制私钥或本地用户表。普通只读查询采用本地验签，因此旧 access 在到期前可能仍能查询本人记录；借书、归还及管理员操作会实时核验账户。

同一个借书 Idempotency-Key 只对应同一 user_id 与 book_id。重复请求返回原记录或继续按原库存操作号核对；编号被用于其他借阅返回 409。归还处于 RETURN_PENDING 时必须重复原编号；RETURNED 后重复归还返回已有终态，不再次释放库存。前端不能超时后生成新编号重新借书或归还。

## 查询参数

| 参数 | 规则 |
| --- | --- |
| status | PENDING、ACTIVE、RETURN_PENDING、RETURNED、FAILED、OVERDUE；OVERDUE 动态筛选到期的 ACTIVE |
| user_id | UUID；仅管理员全量列表；`/me` 只能传本人 UUID |
| book_id | UUID |
| created_from / created_to | `YYYY-MM-DD`，包含上海时区对应的起止自然日 |
| include_archived | 默认 false；仅管理员可设 true |
| page / page_size | 默认 1 / 20，page>=1，page_size 1–100 |
| ordering | created_at、-created_at、due_at、-due_at；默认 -created_at，UUID 稳定次序 |

条件按 AND 组合。未知、重复、非法参数返回 400；超范围页 404。列表结构：`{"count":0,"page":1,"page_size":20,"results":[]}`。

记录响应包含 id、user_id、book_id、username_snapshot、book_title_snapshot、isbn_snapshot、status、display_status、is_overdue、borrowed_at、due_at、returned_at、borrow_days、failure_code、last_error_code、created_at、updated_at、archived_at。密码、JWT、服务凭据不返回。

错误统一为 `{"code":"...","message":"...","details":{},"request_id":"..."}`，响应带 X-Request-ID。401 身份无效，403 权限不足，404 用户/图书/借阅不存在，409 业务或库存冲突，503 依赖服务不可用。已持久化的 PENDING/RETURN_PENDING 因远程结果不明返回 202 和记录状态，恢复命令可核对。明确失败如 OUT_OF_STOCK 返回 409，并保留 FAILED 记录供审计。

## 服务间调用

- `GET USER_SERVICE_URL/internal/v1/users/{actor_id}/eligibility`：BORROW_SERVICE_TOKEN 服务身份 + X-User-Access-Token 用户 access；返回当前 id、username、role、is_active、can_borrow。
- `GET BOOK_SERVICE_URL/internal/v1/books/{book_id}/availability`：独立服务身份；返回 title、isbn、status 和库存快照，供存在性、可借性与历史展示确认。最终扣减以原子预留为准。
- `GET BOOK_SERVICE_URL/internal/v1/books/operations/{operation_key}`：先核对同一操作号。
- `POST BOOK_SERVICE_URL/internal/v1/books/{book_id}/reservations` 或 `/releases`：服务身份、JSON borrow_id、Idempotency-Key UUID。图书服务独占库存真值；失败操作结果也持久记录。

地址由环境变量配置；服务凭据只在忽略的本地 `.env` 或后续部署 Secret 中。公网用户 JWT 不能调用内部库存接口。完整处理和补偿见 [借还流程](workflow.md)，数据库约束见 [数据库说明](database.md)。
