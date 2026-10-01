# 阶段 1：数据模型与约束

本文件是表与约束的设计草案，不是迁移或完整 SQL。每个服务只连接自己的 MySQL 逻辑库；跨库引用保存对方不可变 ID，但不建立跨库外键。时间在数据库中统一保存 UTC，前端和“今日”统计按 `Asia/Shanghai` 展示与计算。

已实现映射：用户字段与 Django 标准字段的对应见 [阶段 3 模型说明](../phase-3/user-service-api.md)；分类、图书和库存操作见 [阶段 4 数据库说明](../phase-4/database.md)；借阅模型、状态及快照见 [阶段 5 数据库说明](../phase-5/database.md)。

## user_db（user-service）

| 表 | 主要字段 | 约束与用途 |
| --- | --- | --- |
| `users` | `id`、`username`、`email`、`password_hash`、`display_name`、`role`、`status`、`created_at`、`updated_at`、`archived_at` | 用户名和规范化邮箱唯一；`role` 为 USER/ADMIN；`status` 为 ACTIVE/DISABLED。密码只存哈希，注册只能成为 USER；归档不抹除历史关联 |

可使用 Django 自定义用户模型承载上述字段，必须在第一次迁移前确定，避免后期替换认证模型。管理员不能删除或停用系统中最后一个有效管理员。普通用户只能修改允许的个人字段，不能修改 `role`、`status` 或其他用户记录。

## book_db（book-service）

| 表 | 主要字段 | 约束与用途 |
| --- | --- | --- |
| `categories` | `id`、`name`、`description`、`created_at`、`updated_at` | 规范化名称唯一；有图书引用（包括归档图书）时拒绝删除，须先迁移分类，保留历史分类关联 |
| `books` | `id`、`title`、`author`、`isbn`、`category_id`、`publisher`、`published_date`、`description`、`total_copies`、`available_copies`、`status`、`created_at`、`updated_at`、`archived_at` | ISBN 规范化后唯一，校验 ISBN-10/13；`0 <= available_copies <= total_copies`；分类为库内外键；状态 ACTIVE/ARCHIVED |
| `stock_operations` | `id`、`operation_key`、`borrow_id`、`book_id`、`kind`、`result`、`created_at` | `operation_key` 唯一；`kind` 为 RESERVE/RELEASE；同一借阅、图书、操作类型唯一；记录库存请求的执行结果，用于幂等与恢复 |

一条 `books` 代表一个 ISBN 对应的书目及其库存，不建立实体副本表。这样可完成册数统计与并发借阅，但不能追踪具体条码或单本损坏状态。只有明确要求单册级管理时才增加副本表。用户可见“可借”条件为 `status=ACTIVE` 且 `available_copies>0`。

管理员调整 `total_copies` 时，新总量不得低于已借出册数，且同步调整 `available_copies`；库存字段不能由普通图书资料编辑接口任意覆盖。借阅期间归档图书后不再公开检索，但内部归还接口仍可释放其库存。当前版本库存真值只保存在 book-service 的 MySQL 库，未实现 Redis。

## borrow_db（borrow-service）

| 表 | 主要字段 | 约束与用途 |
| --- | --- | --- |
| `borrow_records` | `id`、`request_key`、`user_id`、`book_id`、`borrowed_at`、`due_at`、`returned_at`、`status`、`created_at`、`updated_at`、`archived_at` | `request_key` 唯一；状态 PENDING/ACTIVE/RETURN_PENDING/RETURNED/FAILED；用户与图书 ID 无跨库外键；历史以归档代替物理删除 |

`ACTIVE` 与 `RETURN_PENDING` 记录占用一册库存；`PENDING` 是否已占用由 `book-service` 的操作日志判定，不能仅凭借阅表推算库存。`RETURNED`、`FAILED` 不计当前借阅。阶段 5 实际保存 username_snapshot、book_title_snapshot、isbn_snapshot，以便原对象归档后历史记录仍有名称。它们仅用于展示，不作为用户或库存真值。

## 索引与查询

- `users`：用户名、邮箱唯一索引，角色/状态用于管理列表筛选。
- `books`：ISBN 唯一索引，分类与状态索引；书名和作者的初版模糊检索可使用 ORM 条件查询，课程规模下以实际数据量验证性能。
- `borrow_records`：`request_key` 唯一索引；`user_id + created_at`、`book_id + status`、`status + due_at` 支持本人列表、排行与当前借阅。
- `stock_operations`：`operation_key` 和 `(borrow_id, book_id, kind)` 唯一，确保重复请求不重复扣减或归还。

## 删除与数据完整性

用户、图书、借阅记录采用归档字段保留审计链。归档用户不能再登录或新借书，但已有借阅仍可由管理员处理归还。归档图书不允许新借书；已有借阅仍可归还。分类可在无图书引用时删除。所有删除 API 均重新检查后端条件，不能依赖前端确认框保证合法性。

数据库迁移由每个服务独立维护。后续修改模型必须提交 migration 并验证从空库迁移及已有数据升级；阶段 1 尚未生成 migration。
