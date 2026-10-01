# 阶段 11：按最新需求跳过

Prometheus 与 Grafana 属于当前项目暂不完成的选做扩展。本阶段只核对范围，不安装或配置监控组件，不创建 Dashboard，不修改 Docker Compose 加入监控服务。

已检查 README、AGENTS.md、`docs/` 和根目录 `docker-compose.yml`：当前已实现功能仅包括核心业务系统及其 Docker Compose 部署；五项业务统计由 statistics-service 提供，不等同于 Prometheus/Grafana 运行监控。Compose 仍只定义前端、网关、四个 Django 微服务和 MySQL。`deploy/prometheus/` 与 `deploy/grafana/` 保留说明文档，明确为未来可选扩展。

发现阶段 1 需求追踪表的 Docker 行仍包含“监控组件容器化”，已移除该描述，并将阶段 11 标为跳过。未修改业务代码或 Compose，未进入阶段 12。
