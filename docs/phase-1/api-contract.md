# 阶段 1：REST API 合同草案与权限矩阵

本文件约定接口边界和验收行为，具体 JSON Schema 将在各服务实现阶段补充。公开接口经 Nginx 统一前缀 `/api/v1`，内部接口经服务网络访问 `/internal/v1`，仅接受服务身份凭据。除文件和健康端点外，请求与响应均为 JSON。

阶段 3～5 已实现用户、图书与借阅 API，分别见对应阶段接口文档。阶段 6 已实现五项概览统计及三个业务服务的内部汇总接口，详见 [statistics-service 接口文档](../phase-6/statistics-api.md)。

## 通用约定

- 资源 ID 使用服务生成的不可变标识；客户端不得靠顺序推断对象或权限。
- 列表响应统一为 `{ "count": 0, "page": 1, "page_size": 20, "results": [] }`。`page_size` 设置上限，排序字段使用白名单。
- 错误响应统一为 `{ "code": "VALIDATION_ERROR", "message": "可读错误", "details": {}, "request_id": "..." }`。典型 HTTP 状态：400 输入错误、401 未认证、403 无权限、404 不存在、409 冲突或库存不足、503 依赖暂不可用。
- `POST /borrows` 与归还接口要求 `Idempotency-Key`。同一个编号重复提交不得重复扣减或归还库存；处理尚未完成时返回可识别的处理中状态。日志及响应中的 `request_id` 便于跨服务排障。
- 敏感字段如密码哈希、服务凭据、JWT 私钥永不出现在响应中。分页和筛选参数由后端校验；错误参数不能被静默忽略。

## 公开接口

| 方法与路径 | 功能及主要参数 | 权限 | 所属服务 |
| --- | --- | --- | --- |
| `POST /api/v1/auth/register` | 普通用户注册；不接受管理员角色 | 访客 | user |
| `POST /api/v1/auth/login` | 账号密码登录，返回 JWT 与用户摘要 | 访客 | user |
| `POST /api/v1/auth/refresh` | 有效 refresh 换取新 access/refresh，旧 refresh 拉黑 | 有效刷新令牌 | user |
| `POST /api/v1/auth/logout` | 拉黑本人的 refresh | 已登录 | user |
| `GET /api/v1/users/me` | 本人资料 | 已登录 | user |
| `PATCH /api/v1/users/me` | 修改本人允许的资料字段 | 已登录 | user |
| `GET, POST /api/v1/users` | 分页查询、创建用户 | 管理员 | user |
| `GET, PATCH, DELETE /api/v1/users/{id}` | 管理用户；DELETE 为归档 | 管理员 | user |
| `GET /api/v1/books` | 图书列表及筛选 | 已登录 | book |
| `POST /api/v1/books` | 新增图书 | 管理员 | book |
| `GET /api/v1/books/{id}` | 图书详情 | 已登录 | book |
| `PATCH, DELETE /api/v1/books/{id}` | 编辑或归档图书 | 管理员 | book |
| `POST /api/v1/books/{id}/stock-adjustments` | 受控调整总册数和可借册数 | 管理员 | book |
| `GET /api/v1/categories` | 分类列表 | 已登录 | book |
| `POST /api/v1/categories` | 新增分类 | 管理员 | book |
| `GET, PATCH, DELETE /api/v1/categories/{id}` | 分类详情、编辑、删除 | GET 已登录；其余管理员 | book |
| `POST /api/v1/borrows` | 借书，传 `book_id` 和幂等编号 | 已登录且账户可借 | borrow |
| `POST /api/v1/borrows/{id}/return` | 归还该记录；普通用户仅本人 | 本人或管理员 | borrow |
| `GET /api/v1/borrows/me` | 本人借阅列表、状态、历史 | 已登录 | borrow |
| `GET /api/v1/borrows` | 所有借阅记录，分页筛选 | 管理员 | borrow |
| `GET /api/v1/borrows/{id}` | 借阅详情 | 本人或管理员 | borrow |
| `PATCH /api/v1/borrows/{id}` | 受控更正到期日等字段，不直接任意改状态 | 管理员 | borrow |
| `DELETE /api/v1/borrows/{id}` | 归档已结束的借阅记录，不物理清除 | 管理员 | borrow |
| `GET /api/v1/statistics/overview` | 书目、册数、用户和借阅概要 | 管理员 | statistics |

图书列表参数：`title`、`author` 为模糊匹配，`title_exact`、`author_exact` 为精确匹配；`isbn` 为规范化后精确匹配；`category_id`、`status`、`availability` 为精确过滤；多条件按 AND 组合；`page`、`page_size` 分页，`ordering` 仅允许书名、创建时间、出版日期及其倒序。默认仅返回 ACTIVE 图书。`status=ARCHIVED` 列表限经当前角色核验的管理员；公开详情接口仅返回 ACTIVE 图书。

## 内部接口

| 方法与路径 | 调用方 | 用途与约束 |
| --- | --- | --- |
| `GET /internal/v1/users/{id}/eligibility` | borrow | 已实现；当前账户是否存在、有效及可借，含用户名快照；需服务身份和本人 access |
| `GET /internal/v1/users/{id}/authorization` | book（阶段 4）；其他调用方后续授权 | 对敏感管理操作核对当前角色与状态；独立服务凭据加 `X-User-Access-Token` |
| `GET /internal/v1/users/summary` | statistics | 用户总数等汇总，不返回个人明细 |
| `GET /internal/v1/books/{id}/availability` | borrow | 图书当前可借状态；展示用，最终仍以原子预留结果为准 |
| `POST /internal/v1/books/{id}/reservations` | borrow | 按借阅 ID 和唯一操作编号原子预留一册；重复调用返回原结果 |
| `POST /internal/v1/books/{id}/releases` | borrow | 对已预留借阅幂等归还一册；未预留不得凭空增加库存 |
| `GET /internal/v1/books/operations/{operation_key}` | borrow | 网络结果不明时核对库存操作结果 |
| `GET /internal/v1/books/summary` | statistics | ACTIVE 书目数、可借书目数与可借册数聚合 |
| `GET /internal/v1/borrows/summary` | statistics | 已借册数及当前借阅数聚合 |

内部接口不经公开网关暴露，并要求独立服务凭据。当前使用后端鉴权和 Compose 网络隔离，不能单独依赖内网地址。Istio 已在阶段 13 跳过；未来若重新确认服务网格，可在现有鉴权之上扩展。

## 权限矩阵

| 操作 | 访客 | 普通用户 | 管理员 |
| --- | --- | --- | --- |
| 注册与登录 | 可 | 可 | 可 |
| 查看/编辑本人资料 | 不可 | 可 | 可 |
| 查询图书和分类 | 不可 | 可 | 可 |
| 借书与归还本人借阅 | 不可 | 可 | 可 |
| 查看本人借阅 | 不可 | 可 | 可 |
| 查看其他用户借阅 | 不可 | 不可 | 可 |
| 管理用户、图书、分类 | 不可 | 不可 | 可 |
| 更正、归档借阅记录 | 不可 | 不可 | 可 |
| 查看统计与系统运行页面 | 不可 | 不可 | 可 |
| 调用内部库存和汇总接口 | 不可 | 不可 | 不可，只有获授权的服务身份可调用 |

管理员拥有普通用户能力，但不能绕过借阅业务限制。前端菜单和路由守卫与此矩阵保持一致；每个后端操作再独立执行权限与对象归属校验。

## 变更管理

接口实现时逐项补充请求/响应示例、字段长度、分页上限和错误码，并同步测试。若某个接口路径或删除语义需要变更，先更新本合同及受影响前端调用，再进行联调。阶段 3～6 已实现部分以各阶段接口文档及实测记录为准；统计范围已按用户要求缩减为第 1～5 项。
