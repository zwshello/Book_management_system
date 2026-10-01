# 阶段 5：借还协调与恢复

## 借书

1. borrow-service 本地验签 JWT，从 sub 取得不可变用户 UUID，并校验请求 book_id 与 Idempotency-Key。
2. 用独立服务凭据及原用户 access 调 user-service 核对当前账户、角色和资格；用户不存在 404、停用或令牌失效 401、依赖故障 503。
3. 调 book-service 可借接口核对图书存在、ACTIVE、库存>0，并取得 title/ISBN 展示快照；图书不存在 404，不可借 409，依赖故障 503。此查询只是预检查，不能替代原子预留。
4. 在 borrow_db 内按用户 UUID 锁定 borrower_locks 行，计数 PENDING/ACTIVE/RETURN_PENDING，保证并发最多 5 本；先提交 PENDING、请求编号、预留操作号及展示快照。
5. 按预留操作号查询 book-service；尚无记录才用同一操作号原子预留。成功后本地将 PENDING 转 ACTIVE，写 borrowed_at 与 due_at=borrowed_at+30 天；明确库存失败转 FAILED；远程结果不明留 PENDING、HTTP 202。

幂等重放按 request_key 返回相同记录并继续核对；不会新建第二条借阅，也不会用新库存操作号再次扣减。

## 归还

1. 检查借阅 UUID；普通用户只能本人，管理员通过 user-service 核对当前角色。账户被停用时可由当前管理员代还。
2. 在 borrow_db 行锁事务中检查状态。ACTIVE → RETURN_PENDING，并持久化释放操作号；RETURNED 直接返回既有结果，RETURN_PENDING 只接受同一编号。
3. 按原释放操作号先查询 book-service，未执行才调用释放；只有成功预留过的 borrow_id 可释放。book-service 在独立事务中原子加一并记日志，归档图书也可释放。
4. 确认释放成功才将本地状态改 RETURNED，写 returned_at。响应丢失时留 RETURN_PENDING、HTTP 202；绝不根据超时推断结果。

## 部分失败与补偿

借阅意图先落库，因此库存成功但本地 ACTIVE 提交失败时，PENDING 及原操作号仍在。`manage.py reconcile_borrows --min-age 0` 查询操作日志；确认预留成功则完成 ACTIVE，确认释放成功则完成 RETURNED。常规运行默认只扫描超过 5 秒的待处理记录；命令可重复运行，网络仍不可用时保留待处理状态和 last_error_code。可结合定时运行，阶段 5 不安装额外调度组件。

确需取消一个久未确认的 PENDING 时，管理员在本机执行 `manage.py reconcile_borrows --cancel-pending <borrow-id>`。命令先持久化取消意图和唯一释放操作号，再用原预留号核对或完成一次预留；若预留成功，必须以原释放号确认补偿释放，才能标记 FAILED/CANCELLED_COMPENSATED。释放结果未知继续 PENDING，重复运行继续核对；不盲目加库存。此命令只用于人工确认后的单条待处理记录。

标准生产环境通常还会加入持久工作队列、定时重试、告警、死信处置和审计看板。本课程项目沿用阶段 1 已确认的状态机、两侧本地事务、幂等操作日志及手动/可调度恢复命令，便于现场观察跨服务部分失败；没有引入新的消息队列或分布式事务。服务调用不自动重试写请求。

两个真实并发场景已验证：不同用户争最后一册只一人成功；同一用户已借 4 本时并发申请两本只一人成功，达到 5 本上限。故障注入测试验证预留/释放响应丢失、ACTIVE 本地提交失败与补偿释放。结果见 [验证记录](verification.md)。
