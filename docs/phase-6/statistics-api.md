# 阶段 6：statistics-service API 与统计口径

根据用户在阶段 6 的范围调整，本阶段只提供五项基础统计。统计服务没有业务数据库，所有数据均通过受保护的 REST/JSON 汇总接口获取；本页只描述当前存在的统计 API。

## 对外接口

`GET /api/v1/statistics/overview`：仅当前仍有效的管理员可访问。请求使用 user-service 签发的 RS256 access JWT；statistics-service 用公钥本地验签，再向 user-service 核实当前账户状态和角色。普通用户返回 403，未认证返回 401，上游服务不可用或返回非法汇总数据返回 503。接口不接受查询参数。

成功响应示例（数值仅展示格式）：

```json
{
  "user_total": 10,
  "book_total": 8,
  "available_book_titles": 6,
  "available_copies": 21,
  "borrowed_copies": 4,
  "current_borrows": 3,
  "chart": {
    "labels": ["用户总数", "图书书目数", "可借册数", "已借册数", "当前借阅数"],
    "values": [10, 8, 21, 4, 3]
  }
}
```

`chart.labels` 与 `chart.values` 位置一一对应，可直接供 ECharts 柱状图使用。`available_book_titles` 是额外的辅助口径，表示仍有可借库存的书目数；第 3 项“可借图书数量”以 `available_copies` 册数为主，避免把书目数与实体册数混淆。

## 来源与口径

| 阶段 6 指标 | 响应字段 | 数据来源 | 口径 |
| --- | --- | --- | --- |
| 用户总数 | `user_total` | user-service `/internal/v1/users/summary` | 未归档用户数，包含停用用户 |
| 图书总数 | `book_total` | book-service `/internal/v1/books/summary` | 状态为 ACTIVE 的书目数 |
| 可借图书数量 | `available_copies` | book-service `/internal/v1/books/summary` | ACTIVE 书目的 `available_count` 总和 |
| 已借图书数量 | `borrowed_copies` | borrow-service `/internal/v1/borrows/summary` | ACTIVE 与 RETURN_PENDING 记录数；待确认归还仍占用库存 |
| 当前借阅数量 | `current_borrows` | borrow-service `/internal/v1/borrows/summary` | ACTIVE 记录数；不含 PENDING 与 RETURN_PENDING |

## 内部接口与服务调用

`GET /internal/v1/users/summary`、`GET /internal/v1/books/summary`、`GET /internal/v1/borrows/summary` 只接受独立的 `STATISTICS_SERVICE_TOKEN`，用户 JWT 不能直接调用。用户授权核验使用 `GET /internal/v1/users/{id}/authorization`，同时传内部服务凭据和原用户 access token。内部凭据和 JWT 公钥由环境变量注入，密钥不提交仓库。

一次概览请求只调用用户授权核验一次，以及三个服务的汇总端点各一次；业务服务在各自数据库执行聚合，不按用户或书目循环发网络请求。任何必要上游失败均返回 503，不返回可能误导管理员的部分统计。调用超时由 `SERVICE_TIMEOUT` 控制，当前不做 Redis 缓存。

普通用户不能访问完整概览。由于本阶段取消了原第 6～10 项，当前也没有普通用户个人统计接口。前端阶段只能对管理员展示这五项概览，不应调用已删除的路径。
