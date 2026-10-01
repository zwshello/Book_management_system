# 阶段 3：用户服务验证记录

日期：2026-09-30。仅开发 user-service，未进入其他服务业务、前端业务或完整容器部署。

## 配置、检查与迁移

- 修改前已核对 AGENTS、README、阶段 1 需求/架构/数据/API 文档、用户服务代码和脱敏环境配置。仓库仍是初始化后的未提交状态，没有无理由覆盖或删除既有文件。
- 保持 MySQL 8.4.11、user_db/user_app；首次迁移前执行 SHOW TABLES 确认实际 user_db 表数为 0，未使用 SQLite。
- Django 5.2.17、DRF 3.16.1、mysqlclient 2.3.0；新增 Simple JWT 5.5.1、PyJWT 2.15.1、cryptography 50.0.1。pip check 通过。
- manage.py check：0 issues。
- makemigrations accounts：生成 accounts/0001_initial，含自定义 User 和管理员锁表；makemigrations --check --dry-run：No changes detected。
- migrate --noinput：实际 user_db 完成 contenttypes、auth、accounts、token_blacklist 的全部迁移；再次执行 No migrations to apply。
- 正式库有 users、user_administration_lock、组/权限关联、Django 基础表、JWT 标准表；确认没有默认 auth_user；正式库用户数为 0，没有留下测试用户或固定管理员。
- RSA 密钥写入忽略的服务 .env，不打印；再次执行配置脚本确认密钥匹配并保留已有值。

## 自动化测试

```powershell
.\.venv\Scripts\python.exe services\user-service\manage.py test accounts --keepdb --noinput -v 2
```

**43 项测试全部通过，最终约 9.705 秒。** 使用独立 MySQL schema user_db_test，包含正常路径、错误输入、权限边界及真实事务并发测试。

首轮测试的创建用户 fixture 邮箱与管理员重复，唯一性校验正确返回 400；修正 fixture 并补充令牌安全测试后完整重跑通过，没有删除校验或绕过失败。

| 用户要求 | UserApiTests 中的测试 |
| --- | --- |
| 正常注册 | test_registration_hashes_password_and_returns_user |
| 重复用户名 | test_duplicate_username |
| 非法邮箱 | test_invalid_email |
| 密码规则 | test_invalid_password_rules |
| 正常登录 | test_login_and_rsa_claims |
| 密码错误 | test_wrong_login_password |
| 未登录访问 | test_unauthenticated_protected_endpoints |
| 获取本人资料 | test_get_own_profile |
| 普通用户不能访问管理员列表 | test_user_cannot_access_admin_operations |
| 管理员访问列表 | test_admin_list_and_detail |
| 管理员创建 | test_admin_creates_user_and_admin |
| 管理员修改 | test_admin_updates_user_and_password |
| 管理员删除 | test_admin_delete_archives_and_preserves_id |
| 不能自我提权 | test_user_cannot_promote_or_disable_self |
| 模糊查询 | test_fuzzy_username_query |
| 分页 | test_pagination |

补充测试：邮箱规范化/唯一、用户名必填/长度、注册越权、资料校验、管理员非法输入、状态启停、归档保留身份、精确/复合查询、错误参数/排序/分页/UUID、错误结构与 request_id、RSA 声明、刷新轮换/重复令牌拒绝、注销归属、密码修改撤销旧 token、过期/错误签名、refresh 不可作为 access、role 声明不能提权、createsuperuser 的 ADMIN 角色。

ConcurrentAdministratorTests 使用真实 MySQL 与两线程模拟管理员同时降级自身，返回一个 200、一个 409，最终保留一个有效管理员。

## 实际 HTTP

- 标准 runserver 127.0.0.1:8001 --noreload 成功。
- GET /health/live：200，正确服务名。
- 未认证 GET /api/v1/users/me：401 / UNAUTHENTICATED。
- POST 注册提交非法邮箱与短密码：400 / VALIDATION_ERROR。
- 错误体 request_id 与 X-Request-ID 一致。
- 测试服务进程已停止，日志在忽略的 tmp/phase3/runserver.log；开发 MySQL 保持运行。

## 当前边界

- 没有已知阻塞问题。首次管理员需交互 createsuperuser 创建，无默认密码。
- DELETE 归档，前端二次确认在阶段 7 实现。
- logout 撤销 refresh，access 最长仍可用 15 分钟；停用/归档/修改密码会立即拒绝旧 token。
- 前端、网关、内部用户资格/权限 API 未联调；其他服务未来仅拿公钥，敏感操作仍需按阶段 1 核对当前账户，不能跨库查询 users。
- 阶段 4 接口应沿用 UUID/sub、前缀、错误结构和公钥契约。阶段 2 空用户库验证脚本不适用于已经首次迁移的 user_db；请使用本阶段测试命令。
- 完成后停止，等待用户明确指定阶段 4。
