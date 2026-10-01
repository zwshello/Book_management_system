# MySQL 数据设计与所有权

当前持久化只使用 MySQL 8.4。Compose 在一个实例中创建三个逻辑库，并为每个库分配独立业务账户。Django migration 由对应服务独立执行；statistics-service 不维护业务表。

| 所有者 | 数据库 | 主要表 | 说明 |
| --- | --- | --- | --- |
| user-service | `user_db` | `users`、`user_administration_lock`，及 Django 认证/JWT blacklist 表 | 身份、角色、账户状态、密码哈希；管理锁保护最后一个有效管理员 |
| book-service | `book_db` | `categories`、`books`、`stock_operations` | 分类、书目、库存真值和库存操作去重记录 |
| borrow-service | `borrow_db` | `borrow_records`、`borrower_locks` | 借还状态、操作号、展示快照和单用户并发锁 |
| statistics-service | 无 | 无 | 请求时通过三个业务服务的汇总 API 聚合 |

## 主要模型

- **User**：UUID `id`、唯一且归一化的 `username`、唯一且归一化的 `email`、Django 哈希 `password`、`display_name`、`role` (`USER`/`ADMIN`)、`is_active`、`created_at`、`updated_at`、`archived_at`。继承 `AbstractUser`，还带有 Django 标准认证字段。归档会停用账户，不抹除历史 ID。
- **Category**：UUID `id`、`name`、唯一 `normalized_name`、`description`、创建/更新时间。已有图书外键引用时不允许删除。
- **Book**：UUID `id`、`title`、`author`、唯一规范化 ISBN-13、`category`、`publisher`、`published_date`、`description`、`total_copies`、`available_copies`、`status` (`ACTIVE`/`ARCHIVED`)、时间戳。约束 `0 ≤ available_copies ≤ total_copies`；资料编辑不能直接覆盖库存。
- **StockOperation**：UUID 操作 ID、唯一 `operation_key`、跨服务 `borrow_id` 值、库内 `book` 外键、`kind` (`RESERVE`/`RELEASE`)、JSON `result`、时间戳。`borrow_id + book + kind` 唯一，用于同一借还操作的幂等库存变更。
- **BorrowRecord**：UUID `id`、唯一 `request_key`、`user_id`、`book_id`、用户名/书名/ISBN 快照、预留与释放操作号、`status`、借出/应还/归还时间、借阅天数、失败与核对字段、时间戳及归档时间。持久化状态为 `PENDING`、`ACTIVE`、`RETURN_PENDING`、`RETURNED`、`FAILED`；`OVERDUE` 是到期的 `ACTIVE` 记录的动态显示/查询状态。
- **BorrowerLock**：以 `user_id` 为主键的 borrow-service 本地并发锁，不是指向 user-service 的外键。

当前规则默认借期 30 天、每人最多同时借 5 本；可由 borrow-service 环境变量配置。逾期不自动罚款，仍允许归还。

## 为什么不能跨服务读表

每个服务要独立维护模型、迁移、权限和业务规则。如果 borrow-service 直接查询 `user_db` 或修改 `book_db`，用户停用、图书归档和库存并发规则会散落到多个服务，部署与测试也无法独立进行。因此跨服务只保存稳定业务 ID 和必要快照；实时资格、库存变更由数据所有者的受保护 REST/JSON API 完成。数据库账户仅授权本服务的逻辑库。统计服务同样调用汇总 API，不执行跨库 SQL。

迁移与约束的详细实现见 [用户 API](phase-3/user-service-api.md)、[图书数据库](phase-4/database.md)、[借阅数据库](phase-5/database.md)。
