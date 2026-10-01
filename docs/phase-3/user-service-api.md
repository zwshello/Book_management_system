# 阶段 3：user-service 接口与数据模型

本地地址 `http://127.0.0.1:8001`。本文描述已实现的公开用户 API，以及阶段 4 新增并联调的内部当前授权接口；前端与网关尚未联调。路径无结尾斜杠，请求使用 `Content-Type: application/json`，公开保护接口使用 `Authorization: Bearer <access>`。

## 架构与数据模型

独立 Django 项目；`config` 管配置/路由，`accounts` 管模型、Serializer、JWT、权限、查询和视图。只访问 `user_db`，不读取其他服务数据库。使用标准 `AbstractUser` 扩展，首次迁移前设置 `AUTH_USER_MODEL=accounts.User`。

| 字段 | 规则 |
| --- | --- |
| id | 服务生成的不可变 UUID |
| username | 必填，3–150 字符，Unicode 字母/数字及 `@ . + - _`；NFKC 规范化、去首尾空白、casefold；唯一 |
| password | Django 哈希，API 输入 8–128 字符；校验常见密码、纯数字和与用户信息相似性；保留输入空白，响应永不返回密码 |
| email | 必填、合法邮箱、最多 254 字符；去首尾空白并 casefold，唯一 |
| display_name | 可选，最多 100 字符 |
| role | USER / ADMIN；注册固定 USER |
| is_active | 账户启用状态；注册默认 true，只有管理员可修改 |
| created_at / updated_at | 自动时间戳，UTC |
| archived_at | 默认 null；DELETE 设置归档时间并停用，不物理删除 |
| status | 响应只读派生值：ACTIVE / DISABLED，对应 is_active |

表名 `users`。AbstractUser 还保留 last_login、date_joined、is_staff、is_superuser、组/权限等标准字段，它们不向 API 开放写入；业务授权依据 role。Django 的 password 字段对应阶段 1 的 password_hash，不存第二份密码。归档后保留 UUID、用户名和邮箱唯一性，避免历史身份被复用。

`user_administration_lock` 单行锁表串行处理管理员写操作，保护最后一个有效管理员。JWT 刷新记录和黑名单使用 Simple JWT 标准表。

## API 列表

| 方法与路径 | 权限 | 请求 | 成功响应 |
| --- | --- | --- | --- |
| POST /api/v1/auth/register | 公开 | username、email、password；可选 display_name | 201，用户资料；不自动签发 token |
| POST /api/v1/auth/login | 公开 | username、password | 200，access、refresh、user |
| POST /api/v1/auth/refresh | 有效 refresh | refresh | 200，新 access、新 refresh |
| POST /api/v1/auth/logout | 已登录 | 本人的 refresh | 204，拉黑 refresh |
| GET /api/v1/users/me | 已登录且有效 | 无 | 200，本人资料 |
| PATCH /api/v1/users/me | 已登录且有效 | email、display_name 任意组合 | 200，更新资料 |
| GET /api/v1/users | ADMIN | 下表中的查询参数 | 200，分页列表 |
| POST /api/v1/users | ADMIN | username、email、password；可选 display_name、role、is_active | 201，用户资料 |
| GET /api/v1/users/{id} | ADMIN | UUID | 200，用户资料 |
| PATCH /api/v1/users/{id} | ADMIN | username、email、password、display_name、role、is_active 任意组合 | 200，更新资料 |
| DELETE /api/v1/users/{id} | ADMIN | UUID，无请求体 | 204，归档 |

管理接口不返回归档用户，归档后的详情、编辑、再次删除返回 404。前端删除二次确认在阶段 7 实现；当前手工验收应先确认目标 UUID，再发送 DELETE。

资料响应示例（ID 和时间仅为格式示例）：

```json
{
  "id": "0f6f8b10-9c77-4db6-8b65-9dbf85caefcb",
  "username": "reader",
  "email": "reader@example.com",
  "display_name": "读者",
  "role": "USER",
  "is_active": true,
  "status": "ACTIVE",
  "created_at": "2026-09-30T10:00:00Z",
  "updated_at": "2026-09-30T10:00:00Z",
  "archived_at": null
}
```

## 查询与分页

| 参数 | 规则 |
| --- | --- |
| username | 规范化后的精确查询 |
| username_contains | 用户名模糊查询，最多 150 字符 |
| role | USER / ADMIN |
| is_active | 仅 true / false |
| page | 正整数，默认 1 |
| page_size | 1–100，默认 20 |
| ordering | username、-username、created_at、-created_at；默认 -created_at，并用 id 保持稳定排序 |

条件按 AND 组合。未知/重复参数、错误布尔值、非法角色/排序/页大小返回 400；超范围页码返回 404，空结果第一页为 200。

示例：`GET /api/v1/users?username_contains=reader&role=USER&is_active=true&page=1&page_size=20`。

```json
{"count": 0, "page": 1, "page_size": 20, "results": []}
```

## JWT 与后端权限

- Simple JWT、RS256；JWT_PRIVATE_KEY/JWT_PUBLIC_KEY 从环境变量加载，支持转义换行，独立于 DJANGO_SECRET_KEY。配置脚本生成 2048 位 RSA 密钥，仅写入忽略的本地 `.env`，不打印密钥。
- Access 15 分钟，refresh 1 天，轮换后的新 refresh 重新计算有效期。验证签名、到期时间、issuer（library-user-service）、audience（library-services）和 token_type；sub 为 UUID，附 role。
- 本服务每次请求读取当前数据库角色/状态，不信任旧 role 声明。停用/归档后旧 access、refresh 均失效；改密码后用密码哈希指纹拒绝旧 access/refresh。
- refresh 更新当前 role、轮换并拉黑旧 refresh；顺序重复使用旧 refresh 返回 401。logout 只拉黑本人的 refresh，既有 access 到期前仍可使用，除非用户被停用/归档或修改密码。
- 普通用户只能读本人资料，编辑 email/display_name。提交 role、is_active、username、id、is_superuser 等未开放字段返回 400。管理列表/详情/写操作要求当前 ADMIN，普通用户返回 403。
- 最后一个有效 ADMIN 不允许停用、降级、归档，返回 409。管理员写操作在事务内获取单行锁并重新确认操作者权限，防止并发绕过。
- 图书与借阅服务只获得公钥，不复制私钥。阶段 4 已完成当前授权内部接口；阶段 5 已完成 eligibility；summary 留待统计阶段补齐。

配置依据见 [Simple JWT 官方设置](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/settings.html)。

## 阶段 4 新增：内部当前授权

`GET /internal/v1/users/{id}/authorization` 供图书服务核对敏感操作。`Authorization: Bearer <BOOK_SERVICE_TOKEN>` 必须匹配独立服务凭据；`X-User-Access-Token: <access>` 必须是目标 UUID 本人的有效用户令牌。用户 JWT 不能替代服务凭据。

成功返回 200：`{"id":"UUID","role":"ADMIN","is_active":true,"archived_at":null}`。角色取当前用户数据库；停用、归档、改密码后的旧用户令牌返回 401，主体不匹配返回 403。服务凭据错误返回 401、`INVALID_SERVICE_CREDENTIAL`；未配置凭据返回 503。图书服务会将服务凭据故障映射为依赖不可用 503，而不是把它误报为用户未登录。

通过 `scripts/setup_book_auth.py` 在两个服务的忽略 `.env` 中配置匹配的 BOOK_SERVICE_TOKEN，并给图书服务配置公钥；不写入示例文件或文档。阶段 4 新增 6 项内部接口测试，当时用户服务共 49 项；与真实图书服务的联调结果见 [阶段 4 验证记录](../phase-4/verification.md)。

## 阶段 5 新增：借阅资格

`GET /internal/v1/users/{id}/eligibility` 接受独立 BORROW_SERVICE_TOKEN 服务身份与 X-User-Access-Token 用户 access。验证签名、主体一致、当前用户状态和密码指纹；成功返回 id、username、当前 role、is_active 与 can_borrow。不存在的用户 404，停用或旧密码令牌 401，服务身份无效 401。借阅上限由 borrow-service 在自己的数据库内锁定用户 UUID 后计算；此接口不跨库查询借阅记录。

`scripts/setup_borrow_auth.py` 为用户、图书、借阅服务配置匹配的 BORROW_SERVICE_TOKEN，并仅给借阅服务复制 JWT 公钥。新增 5 项资格接口测试，用户服务当前共 54 项测试；三个真实服务联调结果见 [阶段 5 验证记录](../phase-5/verification.md)。阶段 3 的验证记录保留当时的 43 项历史结果。

## 错误与状态码

未知或只读字段不静默忽略。输入校验错误为 400；并发唯一约束冲突 409；数据库暂不可用 503，不暴露 SQL 或密码。所有响应附 X-Request-ID，错误体使用同一编号。

```json
{
  "code": "VALIDATION_ERROR",
  "message": "输入不合法，请检查 details。",
  "details": {"email": ["邮箱已存在。"]},
  "request_id": "55c08b41-3bd4-46e8-8f9d-0ba2e20ce47f"
}
```

常见状态：200 查询/更新/签发，201 创建，204 归档/退出，400 输入错误，401 未登录/密码错误/无效令牌，403 权限不足，404 用户/页码不存在，405 方法不支持，409 冲突，415 非 JSON，503 数据库暂不可用。

## Windows 启动与验证

从项目根目录运行，每条命令失败时先修复再继续：

```powershell
.\.venv\Scripts\python.exe -m pip install -r services\user-service\requirements.txt
.\.venv\Scripts\python.exe scripts\setup_dev_env.py
.\.venv\Scripts\python.exe scripts\setup_user_jwt.py
docker compose up -d --wait --wait-timeout 120 mysql
# 已有卷不会自动执行新增初始化脚本；补建测试库与授权：
docker compose exec -T mysql bash /docker-entrypoint-initdb.d/01-databases.sh
.\.venv\Scripts\python.exe services\user-service\manage.py check
.\.venv\Scripts\python.exe services\user-service\manage.py migrate --noinput
.\.venv\Scripts\python.exe services\user-service\manage.py test accounts --keepdb --noinput -v 2
```

测试使用独立 `user_db_test`（MYSQL_TEST_DATABASE），不写入实际 user_db。首次管理员通过交互命令创建，Manager 自动设置 ADMIN，无预置账户/密码：

```powershell
.\.venv\Scripts\python.exe services\user-service\manage.py createsuperuser
.\.venv\Scripts\python.exe services\user-service\manage.py runserver 127.0.0.1:8001
```

手工演示：首次管理员 → 注册普通用户 → 分别登录 → 获取/修改本人资料 → 普通用户访问列表确认 403 → 管理员 CRUD、停用/启用 → 模糊/复合查询和分页 → 确认目标后归档 → 弱密码/重复用户名 400、停用账户 401。

可按需运行 `manage.py flushexpiredtokens` 清理过期刷新记录，本阶段未新增定时任务。实测结果见 [验证记录](verification.md)。阶段 3 完成后停止，不自动进入阶段 4。
