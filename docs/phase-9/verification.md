# 阶段 9：Redis 暂缓与当前版本范围核对

> 后续阶段 10 又明确暂缓 Prometheus、Grafana、Kubernetes 与 Istio，并已完成核心 Docker Compose 部署；本页其余内容记录阶段 9 当时的核对结果。

2026-10-01 用户调整验收范围：当前版本不实现 Redis、NoSQL 缓存、图书查询缓存、Dashboard 缓存或 Redis 容器。本阶段仅清理尚未使用的占位配置和同步文档，不新增业务能力。

## 残留盘点与处理

| 范围 | 检查结果及处理 |
| --- | --- |
| Python 依赖 | 四份 `requirements.txt` 均无 Redis 客户端或 `django-redis`，无需删除依赖。 |
| Django 配置与业务代码 | 四服务无 Redis 连接、`CACHES` 配置或缓存读写代码，未改业务实现。 |
| 环境变量 | 根目录、book-service、statistics-service 的 `.env.example` 各移除 `REDIS_HOST`、`REDIS_PORT`；三个对应的未提交本地 `.env` 仅移除相同占位行，其他配置与密钥保持不变。 |
| Docker | 当前 `docker-compose.yml` 原本只定义 MySQL；没有 Redis 容器或 Redis 卷，故未修改 Compose。Docker 阶段说明明确不加入 Redis。 |
| 文档与协作规则 | README、AGENTS、阶段 1 需求追踪/架构/模型/借还流程、阶段 2～6 的相关说明和阶段 8 联调记录均已区分历史规划与当前验收范围。历史思路保留为可选扩展，不再列入当前验收或阶段 10 部署。 |

## 当前数据方案与统计

一个 MySQL 实例分别承载 `user_db`、`book_db`、`borrow_db`。三个业务服务只访问自己的库；跨服务通过受保护 REST/JSON API 协作。statistics-service 不持久化业务数据，通过用户、图书和借阅服务的聚合接口实时提供五项管理员统计：用户总数、图书总数、可借图书册数、已借册数、当前借阅数。早期额外统计设想不属于当前范围。

## 验证

四个 Django 项目的 `manage.py check` 均通过。前端 `npm run build` 通过 TypeScript 检查与 Vite 构建，仍有既有的主包体积提示。`pip check` 未发现依赖冲突，`docker compose config --quiet` 通过。开发用 MySQL 容器 `library-dev-mysql-1` 经 `docker compose up -d --wait --wait-timeout 120 mysql` 启动并报告 Healthy。基于 MySQL 测试库运行四个服务的测试：user-service 56/56、book-service 56/56、borrow-service 22/22、statistics-service 6/6，共 140/140 通过；测试期间各服务的 Django system check 均未报告问题。

## 阶段 10 注意事项

阶段 10 的 Compose 与 Dockerfile 只部署当前验收组件，不添加 Redis 服务、卷、Secret 或 `REDIS_*` 变量。三个 MySQL 逻辑库与专用账户仍须隔离；statistics-service 无业务库。容器内服务 URL 使用服务名注入，JWT 公钥和内部服务凭据由安全配置提供。迁移、健康检查、MySQL 持久化以及阶段 8 的 A/B/C 流程应实际验证。Kubernetes 已按后续用户决定暂缓。
