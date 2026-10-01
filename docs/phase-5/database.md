# 阶段 5：borrow_db 数据模型

borrow-service 只使用 borrow_db / borrow_app，测试用 borrow_db_test。没有 user_db、book_db 权限，也不建立跨库 ForeignKey。用户和图书仅以 UUID 保存；username_snapshot、book_title_snapshot、isbn_snapshot 保证原对象归档后历史记录仍可辨认。

| 表 | 主要字段和约束 |
| --- | --- |
| borrower_locks | user_id UUID 主键；只作为本地并发计数互斥行，不复制用户资料 |
| borrow_records | id UUID 主键；request_key UUID 唯一；user_id、book_id UUID；展示快照；reservation_key UUID 唯一；release_key UUID 可空且唯一；status；borrowed_at、due_at、returned_at；borrow_days；cancel_requested；failure_code、last_error_code、last_request_id；created_at、updated_at、archived_at |

状态仅 PENDING、ACTIVE、RETURN_PENDING、RETURNED、FAILED；OVERDUE 按 ACTIVE 与 due_at 动态派生。CHECK 约束检查状态值、借还时间与状态的组合、due_at 晚于 borrowed_at、归还时间不早于借出时间、归档仅终态，以及归还状态必须有 release_key。索引支持 user_id/status、book_id/status、status/updated_at 恢复扫描和 status/due_at 逾期筛选。

一条记录最多一笔成功预留和释放：跨服务操作号本地唯一，图书服务另外用 operation_key 与 (borrow_id,book_id,kind) 双重唯一保证库存幂等。PENDING 计入用户上限，防止结果不明时继续申请超过 5 本。归档保留借阅历史与库存操作关联；数据库业务表不包含用户密码、图书库存或跨库外键。

`borrowing/0001_initial` 已实际迁入 MySQL borrow_db。Django 框架 auth/contenttypes 技术表由独立项目框架迁移创建，但 auth_user 不用作业务身份。测试及真实 HTTP 联调用 *_test 隔离库，结束后定向清理本轮数据。
