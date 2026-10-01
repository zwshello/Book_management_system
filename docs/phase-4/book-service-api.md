# 阶段 4：book-service API

本地地址 `http://127.0.0.1:8002`。路径无尾斜杠，JSON 请求，公开接口使用 user-service 签发的 `Authorization: Bearer <access>`。只访问 book_db；没有复制用户数据库或登录接口。字段保持阶段 1 的 `published_date/total_copies/available_copies`，不引入第二套 count 字段。

## 公开接口

| 方法与路径 | 权限与行为 |
| --- | --- |
| GET /api/v1/categories | 已登录，分类分页列表，可按 name 模糊查询 |
| POST /api/v1/categories | 当前管理员，新增分类，201 |
| GET /api/v1/categories/{id} | 已登录，分类详情 |
| PATCH /api/v1/categories/{id} | 当前管理员，编辑名称/描述 |
| DELETE /api/v1/categories/{id} | 当前管理员，无图书引用才物理删除，204；有引用 409 |
| GET /api/v1/books | 已登录，图书列表，默认 ACTIVE |
| POST /api/v1/books | 当前管理员，新增图书，201 |
| GET /api/v1/books/{id} | 已登录，ACTIVE 图书详情；归档或不存在 404 |
| PATCH /api/v1/books/{id} | 当前管理员，修改资料或合法 status；库存字段禁止直接提交 |
| DELETE /api/v1/books/{id} | 当前管理员，归档并保留库存、ISBN及操作关联，204 |
| POST /api/v1/books/{id}/stock-adjustments | 当前管理员，仅接收新 total_copies，自动保留已占用量 |

分类名称 1–100 字符，NFKC、合并空白、去首尾空白，casefold 后唯一；保留显示大小写。描述最多 10000 字符。图书 title/author 必填且不允许空白，最多 200 字符，publisher 最多 200 字符，description 最多 10000 字符；published_date 为合法日期或 null；category 是已有分类 UUID。

新增图书示例：

```json
{
  "title": "Python 入门",
  "author": "示例作者",
  "isbn": "0-306-40615-2",
  "category": "6d259621-2a5e-45a9-bd5b-b49c9d6f4559",
  "publisher": "示例出版社",
  "published_date": "2020-01-01",
  "description": "示例书目",
  "total_copies": 3,
  "available_copies": 3,
  "status": "ACTIVE"
}
```

UUID仅为格式示例，需要先创建真实分类。ISBN 去空白/连字符，验证 ISBN-10/13 校验位，ISBN-13 要求 978/979 前缀；合法 ISBN-10 转换为等价 ISBN-13 存储，防止两个表示重复创建。唯一性包括归档书目；本示例存储为 9780306406157。验证格式与校验位，不查询出版机构登记信息。规则参考 [国际 ISBN 机构](https://www.isbn-international.org/content/isbn-calculator)。

库存整数范围 0–2147483647，available_copies 不超过 total_copies；创建时总量默认 0，可借量省略则等于总量。资料 PATCH 拒绝两个库存字段。调整总量示例 `{"total_copies": 5}`：已占用量为原 total_copies - available_copies，新总量不得低于该值，否则 409，新可借量为新总量 - 已占用量。

状态仅 ACTIVE / ARCHIVED；设置 ARCHIVED 同步归档时间，设置 ACTIVE 清除归档时间。管理员可以明确查询归档列表并 PATCH 资料/状态；普通用户不能查询归档列表。DELETE 不受已有预留阻止，因为是归档：禁止新预留，既有预留仍可释放。分类在任何图书引用下拒绝物理删除，包括归档图书，需先迁移其分类以保留历史关联。前端删除确认属于阶段 7。

## 查询、分页与排序

| 参数 | 行为 |
| --- | --- |
| title / author | 不区分大小写的模糊匹配 |
| title_exact / author_exact | 不区分大小写的完整匹配 |
| isbn | 规范化后的精确匹配，支持 ISBN-10 查询等价 13 位书目 |
| category_id | 分类 UUID 精确过滤；分类不存在时空结果 |
| status | ACTIVE / ARCHIVED；默认 ACTIVE，ARCHIVED 仅当前管理员 |
| availability | available：ACTIVE 且库存>0；unavailable：当前状态集合中不满足可借条件的书目 |
| page / page_size | 默认 1 / 20，page>=1，page_size 为 1–100 |
| ordering | title、-title、created_at、-created_at、published_date、-published_date；默认 -created_at，并用 UUID 稳定排序 |

所有条件按 AND 组合：`GET /api/v1/books?title=Python&category_id=<uuid>&availability=available&page=1&page_size=20&ordering=title`。

分类查询支持 name、page、page_size、ordering（name、-name、created_at、-created_at）。未知参数、重复参数、非法排序/状态/分页/ISBN返回 400；超范围页返回 404，空结果第一页返回 200。

分页结构 `{"count":0,"page":1,"page_size":20,"results":[]}`。图书响应还包含 category_name、created_at、updated_at、archived_at。

## JWT 与当前权限

沿用 user-service RS256、公钥、issuer、audience、sub UUID、role 与 access 类型。本服务采用 [Simple JWT 无状态身份](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/stateless_user_authentication.html)，不读取本地 auth_user 或 user_db；不持有签名私钥，不签发用户 token。

普通只读查询本地验签。管理员写操作和归档列表查询，先检查 token role=ADMIN，再用独立 BOOK_SERVICE_TOKEN 调用 `GET /internal/v1/users/{id}/authorization`，并转发用户 access 至 X-User-Access-Token。用户服务验证真实 token、当前密码指纹、账户状态和角色；降级 403、禁用或改密码后旧 token 401；依赖失败或服务凭据配置错误 503，不执行写入。不缓存授权，不自动重试写操作。

普通只读接口不会逐次查询用户服务，因此停用/改密码/退出后的旧 access 在有效期内仍可能用于图书读取，最长到 token 到期。敏感管理写入实时核对。这是阶段 1 区分本地验签与敏感动作核对的设计边界。

## 内部库存接口

仅接受 `Authorization: Bearer <BORROW_SERVICE_TOKEN>` 服务身份；普通用户和管理员 JWT 均不能调用。

| 方法与路径 | 请求与返回 |
| --- | --- |
| GET /internal/v1/books/{id}/availability | 状态、总量、可借量、available；归档可查，供后续归还核对 |
| POST /internal/v1/books/{id}/reservations | JSON borrow_id UUID + Idempotency-Key UUID；原子预留一册 |
| POST /internal/v1/books/{id}/releases | 同上；存在成功预留才能原子释放一册 |
| GET /internal/v1/books/operations/{operation_key} | 返回记录结果；未执行 404 |

成功为 200，示例：

```json
{
  "success": true,
  "code": "OK",
  "operation_key": "6fab7925-3a3a-44f9-94f8-bcfe7f13f437",
  "borrow_id": "4d672382-c3c5-4cdf-873f-1f60dc99fb90",
  "book_id": "d4a3c6a8-5ea2-4cc5-aec8-03d7fb710f0a",
  "kind": "RESERVE",
  "total_copies": 3,
  "available_copies": 2
}
```

图书行锁、库存更新、操作记录位于同一 MySQL 事务。相同 key、book、borrow、kind 返回原快照，不重复改变库存；同一 key 不同参数、同一借阅/书目/类型换 key 返回 409。业务失败也持久记录，重放仍返回原失败，避免一次失败重试突然预留成功。失败包括 OUT_OF_STOCK、BOOK_ARCHIVED、RESERVATION_NOT_FOUND、STOCK_CONFLICT，HTTP 409；details.operation 保存原结果。

操作记录中的库存是执行时快照，不是当前库存；当前库存读 availability。网络结果不明时查询原 operation_key 或重试相同请求，不能换 key 或盲目释放。借阅资格、借阅记录、用户上限和恢复任务属于阶段 5。

阶段 5 联调将 availability 响应补充 `title` 和 `isbn`，供借阅服务保存历史展示快照；冲突响应 `details.operation` 保持原生 JSON 布尔值与整数，便于按原操作号解释库存失败。借阅调用链与验证见 [阶段 5 流程](../phase-5/workflow.md)。

## 错误、配置与验证

保持统一错误结构 code/message/details/request_id 和 X-Request-ID。400 校验，401 身份/token，403 权限，404 资源，409 冲突，503 依赖不可用；错误不暴露 SQL、密码或服务凭据。

根目录 Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip install -r services\book-service\requirements.txt
.\.venv\Scripts\python.exe scripts\setup_dev_env.py
.\.venv\Scripts\python.exe scripts\setup_user_jwt.py
.\.venv\Scripts\python.exe scripts\setup_book_auth.py
docker compose up -d --wait --wait-timeout 120 mysql
docker compose exec -T mysql bash /docker-entrypoint-initdb.d/01-databases.sh
.\.venv\Scripts\python.exe services\user-service\manage.py migrate --noinput
.\.venv\Scripts\python.exe services\book-service\manage.py migrate --noinput
.\.venv\Scripts\python.exe services\book-service\manage.py check
.\.venv\Scripts\python.exe services\book-service\manage.py test catalog --keepdb --noinput
.\.venv\Scripts\python.exe services\user-service\manage.py test accounts --keepdb --noinput
.\.venv\Scripts\python.exe scripts\verify_phase4_http.py
```

每步失败先修复再继续。测试用 book_db_test / user_db_test，不写业务库；真实 HTTP 验证占用 8001/8002，应先关闭自己的开发进程。setup_book_auth 只复制公钥，并配置匹配服务凭据，已有不同配置会报错而不是覆盖；真实凭据仅在忽略的 .env。现有卷补执行初始化只是补建库/授权，不删除数据或重置已有密码。

实际开发在两个终端运行 user-service :8001 和 book-service :8002 的标准 runserver；首次管理员按阶段 3 createsuperuser 创建。配置 service URL 从环境变量读取，后续容器部署要使用服务 DNS 名。阶段 9 用户已暂缓 Redis；前端业务已于阶段 7 实现，完整容器化仍待阶段 10。验证及数据模型见 [验证记录](verification.md)、[数据库说明](database.md)。
