# Docker

根目录 `docker-compose.yml` 在阶段 10 已包含前端、Nginx 网关、四个 Django 微服务及 MySQL 8.4。公共 Django Dockerfile 位于 `django/Dockerfile`，MySQL 初始化脚本位于 `mysql/init/`。当前只使用 MySQL 持久化，不加入 Redis、Prometheus 或 Grafana。启动与验证见根目录 [README](../../README.md) 和[阶段 10 验证记录](../../docs/phase-10/verification.md)。
