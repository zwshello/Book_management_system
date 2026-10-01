# Docker Compose 部署与验证

当前 Docker 部署只包含课程必做的七个组件：frontend、gateway、user-service、book-service、borrow-service、statistics-service、mysql。已在 Windows + Docker Desktop 环境验证。Redis、Prometheus、Grafana、Kubernetes、Istio 均未部署。

## 首次准备（项目根目录，PowerShell）

先安装 Docker Desktop、Python 3.11+ 和四份后端依赖，创建本地虚拟环境；已有本地 `.env` 与密钥时不要重新覆盖。

```powershell
python -m venv .venv
foreach ($service in @('user-service','book-service','borrow-service','statistics-service')) {
  .\.venv\Scripts\python.exe -m pip install -r "services\$service\requirements.txt"
}
.\.venv\Scripts\python.exe scripts\setup_dev_env.py
.\.venv\Scripts\python.exe scripts\setup_user_jwt.py
.\.venv\Scripts\python.exe scripts\setup_book_auth.py
.\.venv\Scripts\python.exe scripts\setup_borrow_auth.py
.\.venv\Scripts\python.exe scripts\setup_statistics_auth.py
docker compose config --quiet
docker compose build
docker compose up -d --wait --wait-timeout 180
docker compose ps
```

这些脚本生成并核对**未提交**的根目录和服务 `.env`、JWT RSA 密钥与服务凭据，不覆盖已有配置。`docker-compose.yml` 从 `.env` 读取 MySQL 密码，镜像构建由 `.dockerignore` 排除本地密钥。首次管理员可用 `docker compose exec user-service python manage.py createsuperuser` 创建，密码在交互提示中输入。

默认浏览器入口为 `http://127.0.0.1:8080/`。若 8080 被占用，在根目录 `.env` 设置 `GATEWAY_PORT=8088` 后重新启动；实际地址以本机配置为准。浏览器无需访问四个后端端口。Compose 内部在 `library-net` 网络使用服务名，例如 `http://book-service:8002`；容器内不能用 `localhost` 指代另一个服务。

## 容器与数据

| 服务 | 作用 | 对主机开放 |
| --- | --- | --- |
| `frontend` | Nginx 提供 Vue build 静态文件及前端路由回退 | 否 |
| `gateway` | Nginx 统一 Web/API 入口和路径转发 | `127.0.0.1:${GATEWAY_PORT:-8080}` |
| `user-service` | JWT、账户、角色、用户管理 | 否 |
| `book-service` | 分类、书目、库存 | 否 |
| `borrow-service` | 借还记录和跨服务协调 | 否 |
| `statistics-service` | 汇总五项业务统计 | 否 |
| `mysql` | MySQL 8.4，三个逻辑库 | `127.0.0.1:${MYSQL_PORT:-3306}` 仅本机开发连接 |

MySQL volume 为 `library-dev_mysql-data`，`docker compose down` 不删除它。**不要**用 `docker compose down -v` 作为日常停止命令。MySQL 健康检查确认三个业务库可用；三个持久化服务启动时执行 `migrate --noinput`，再启动应用。gateway 等待上游健康，但 `/gateway/health` 只检测网关进程，不能替代业务测试。

## 日常命令与复测

```powershell
docker compose up --build -d --wait --wait-timeout 180
docker compose ps
docker compose logs --tail 100 gateway
$env:PHASE10_GATEWAY_URL='http://127.0.0.1:8080' # 端口不同则修改
.\.venv\Scripts\python.exe scripts\verify_phase10_compose.py
docker compose down
```

业务脚本通过 gateway 创建有独立前缀的临时测试数据，验证管理员、普通用户、查询、借还、权限、输入校验及五项统计，然后清理自己的记录。只对本机开发数据库运行，不能用于生产数据。更新单个容器后，gateway 使用 Docker DNS 动态解析服务名；仍应再跑脚本确认路径转发与业务调用。Nginx 配置语法可执行 `docker compose exec -T gateway nginx -t` 验证。

## 常见问题

| 现象 | 检查与处理 |
| --- | --- |
| 8080/3306 端口被占 | 修改未提交根目录 `.env` 中的 `GATEWAY_PORT` / `MYSQL_PORT`，然后 `docker compose up -d --wait` |
| `compose config` 缺少密码 | 运行配置脚本，核对根目录和服务 `.env`，不要把真实密码写进 `.env.example` |
| MySQL healthy 但应用连接失败 | 核对各服务数据库名、账户与密码；已有 volume 的数据库密码不会因修改 `.env` 自动更新 |
| 容器 unhealthy 或退出 | `docker compose ps` 与 `docker compose logs --tail 100 <service>`；优先找迁移、配置、上游故障 |
| 镜像拉取或构建失败 | 检查 Docker Desktop 网络和磁盘；现有 Dockerfile 使用公开的 Docker 官方镜像镜像源；不要删业务 volume 解决构建问题 |
| 页面可打开但 API 失败 | 检查 gateway 日志和四服务健康；运行完整 HTTP 验证脚本，单看 `/gateway/health` 不够 |

架构及数据库所有权见 [architecture.md](architecture.md)、[database.md](database.md)；阶段 10 与 14 的实际执行记录见 [阶段 10 验证](phase-10/verification.md)、[完整测试报告](test-report.md)。
