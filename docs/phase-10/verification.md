# 阶段 10：Docker Compose 核心系统验证

日期：2026-10-01。当前只部署 Vue 前端、Nginx 网关、四个 Django 微服务和 MySQL。Redis、Prometheus、Grafana、Kubernetes 与 Istio 均不在本阶段范围。

## 配置与边界

- 根目录 `docker-compose.yml` 创建 `library-net` 网络。gateway 是唯一公开的 Web/API 入口；前端和四个 Django 服务均不发布宿主机端口。MySQL 为兼容本机开发，仅绑定宿主机 `127.0.0.1:3306`。
- `gateway/nginx.conf` 将 `/api/v1/auth`、`/api/v1/users`、`/api/v1/books`、`/api/v1/categories`、`/api/v1/borrows`、`/api/v1/statistics` 转发到对应服务；其他路径转发给前端 Nginx。前端使用同源 `/api/v1`，无跨域调用。
- Django 四服务使用 `deploy/docker/django/Dockerfile` 多阶段构建；前端经 Node 构建后用 Nginx 提供静态文件，gateway 有独立 Nginx 镜像。Docker build 不复制任何本地 `.env`；运行时通过 Compose `env_file` 注入未提交的服务凭据。
- 容器内 `MYSQL_HOST=mysql`；跨服务 URL 如 `http://book-service:8002`。MySQL 一个实例承载 `user_db`、`book_db`、`borrow_db`，账户按库隔离。statistics-service 不连接业务数据库。
- MySQL 数据使用命名卷 `library-dev_mysql-data`。MySQL 的健康检查确认三个业务库可访问；三个业务服务等待数据库健康后执行 migration，再提供 HTTP 服务。gateway 等待全部业务服务与前端健康。

## 实际执行结果

| 验证 | 结果 |
| --- | --- |
| `docker compose config --quiet` | 通过 |
| `docker compose build --quiet` | 六个应用镜像全部构建成功 |
| `docker compose up --build -d --wait --wait-timeout 180` | 七个容器全部启动并通过健康检查 |
| `docker compose ps` | frontend、gateway、user-service、book-service、borrow-service、statistics-service、mysql 均 `Up (healthy)`；gateway 绑定本机 `127.0.0.1:8088` |
| Django `manage.py check` | 四服务均无问题 |
| Django `manage.py migrate --check` | 用户、图书、借阅三个业务库均无待执行 migration |
| `docker volume inspect library-dev_mysql-data` | 命名卷存在，驱动为 `local` |
| 镜像内密钥文件检查 | user-service 镜像内无 `/app/.env`；运行时环境单独注入 |

运行 `scripts/verify_phase10_compose.py`，通过 gateway 的真实 HTTP 请求创建唯一标记的临时管理员和业务样本，完成后清理样本：

- gateway 健康接口、Vue `/login` 路由回退及构建后的 JS 资源均返回 200。
- 管理员登录，创建和查询分类；创建图书、组合查询、分页、排序、修改及删除；创建、查询、修改、删除用户。
- 普通用户登录，查询和模糊搜索图书、查看详情、借书、查看本人记录、还书；图书库存随借还正确变化。
- 管理员查询用户和全部借阅记录；统计接口返回用户总数、图书总数、可借册数、已借册数、当前借阅数五项真实数据，借还前后数值变化正确。
- 普通用户调用用户管理、图书写接口及管理员统计均为 403；未认证管理请求为 401；非法输入为 400。

## 构建期间发现并处理的问题

1. 本机 Docker Hub 认证端点无法连接。应用 Dockerfile 改用公共 ECR 的 Docker 官方 Python、Node、Nginx 镜像；镜像已实际拉取并构建。运行环境仍须能访问该镜像源及 Python/npm 依赖源。
2. 首次并行导出四个后端镜像时，宿主机磁盘写满，Docker 存储出现只读错误。临时清理本项目可重建的 `frontend/node_modules` 后恢复空间、重启 Docker Desktop，并将 Django 镜像改成多阶段构建；之后逐个构建成功，最终完整 `docker compose build --quiet` 也通过。验证后已运行 `npm ci` 恢复本机依赖，`npm run build` 再次通过。
3. 本机已有 `ApplicationWebServer` 占用 8080。未终止其他进程；本地未提交的根目录 `.env` 增加 `GATEWAY_PORT=8088`，所有验收经 `http://127.0.0.1:8088` 运行。全新环境若 8080 空闲，可使用默认端口。

## 当前限制

本阶段验证的是开发环境 Compose 部署和经 gateway 的真实 HTTP 业务链，未加入监控或编排平台。前端静态文件和路由回退已验证；阶段 8 的浏览器逐项交互记录仍见 `docs/integration-test.md`。构建需要留出 Docker 镜像与缓存空间；验证结束时宿主机 C 盘可用空间约 1.6 GB，已将未使用的 Docker 构建缓存限制到 1 GB，但 Docker 虚拟磁盘文件未自动缩小，后续重新构建前应检查可用空间。当前容器保持运行；`docker compose down` 会停止容器并保留 MySQL 卷。
