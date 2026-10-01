# Gateway 基础配置

阶段 10 使用 `Dockerfile` 和 `nginx.conf` 运行 Nginx 统一入口。`/api/v1/auth`、`/api/v1/users`、`/api/v1/books`、`/api/v1/categories`、`/api/v1/borrows`、`/api/v1/statistics` 按 Compose 服务名转发，其他路径转发到 frontend。`nginx.conf.example` 仅保留为阶段 2 的历史草案；实际部署以 `nginx.conf` 为准。
