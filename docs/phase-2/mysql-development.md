# 阶段 2：Windows 开发用 MySQL

> 本页保留阶段 2 单独启动 MySQL 的开发说明。阶段 10 的完整容器启动和网关入口见根目录 README；以下“当前没有应用容器”等表述仅指阶段 2 当时。

当前方案沿用阶段 1：一个 MySQL 8.4 实例，三个独立 database（MySQL 中 schema 与 database 在此等价）。统计服务初期不持久化业务事实，通过后续 API 汇总，因此不创建第四个业务库，也未改用 SQLite。

## 当前环境变量

每个 Django 项目的 `settings.py` 从本服务目录 `.env` 加载配置；已设置的进程环境变量优先。根目录 `.env` 供 Compose 使用，不会自动注入本地 Django。

| 配置 | user-service | book-service | borrow-service | statistics-service |
| --- | --- | --- | --- | --- |
| MYSQL_HOST | 127.0.0.1 | 127.0.0.1 | 127.0.0.1 | 不适用 |
| MYSQL_PORT | 3306 | 3306 | 3306 | 不适用 |
| MYSQL_DATABASE | user_db | book_db | borrow_db | 无业务库 |
| MYSQL_USER | user_app | book_app | borrow_app | 不适用 |
| MYSQL_PASSWORD | 本服务 `.env` 的本地随机值 | 同左 | 同左 | 不适用 |
| Django 端口 | 8001 | 8002 | 8003 | 8004 |

根目录 Compose 读取 `MYSQL_ROOT_PASSWORD`、`USER_MYSQL_PASSWORD`、`BOOK_MYSQL_PASSWORD`、`BORROW_MYSQL_PASSWORD` 和 `MYSQL_PORT`。配置脚本保证对应服务的 `MYSQL_PASSWORD` 与 Compose 中账号密码匹配。根目录通用的 `MYSQL_DATABASE/MYSQL_USER/MYSQL_PASSWORD` 只是示例，不由 Compose 消费。账号仅拥有自己的开发库和自己的迁移验证库权限，Django 不使用 root。

## PowerShell 启动命令

Docker Desktop 必须正在运行。当前机器已有根目录 `.venv` 及 MySQL 驱动；新机器按 README 安装各份 requirements。

```powershell
Set-Location 'C:\Users\Mr.zhang\Desktop\Book_management_system'
.\.venv\Scripts\python.exe scripts\setup_dev_env.py
if ($LASTEXITCODE -ne 0) { throw '本地配置生成失败，已有文件未覆盖' }
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose 配置无效' }
docker compose up -d --wait --wait-timeout 120 mysql
if ($LASTEXITCODE -ne 0) { throw 'MySQL 启动或健康检查失败，请查看容器日志' }
docker compose ps
```

镜像为 `mysql:8.4`，本次实际版本为 8.4.11。容器名默认 `library-dev-mysql-1`，端口仅绑定 `127.0.0.1:3306`，数据卷为 `library-dev_mysql-data`。初始化脚本创建三个业务库、三个独立验证库及三个专用账号。健康检查同时验证 root 可连接且三个开发库已存在。当前没有应用容器、Redis、网关或监控容器；不属于阶段 10 的完整部署。

配置脚本只创建缺失的 `.env`，不覆盖已有文件；它检查已有服务配置是否与 Compose 一致。密码使用随机十六进制值，初始化脚本拒绝非 32–128 位小写十六进制的服务密码，避免 SQL 拼接歧义。示例文件只含占位值，真实值只在 Git 忽略的本地 `.env` 中。不要用 `docker compose config` 的完整输出分享配置，因为该输出可能展开密码；使用 `--quiet`。

## 实际连接、迁移和启动验证

```powershell
.\.venv\Scripts\python.exe scripts\verify_stage2_mysql.py
```

该脚本真实执行：

1. 四个项目的 `manage.py check`。
2. 前三个项目通过 Django MySQL backend 执行 `SELECT DATABASE(), VERSION(), 1`。
3. 各服务访问其他服务库必须收到 MySQL 1044 权限错误。
4. 通过临时子进程环境变量 `MYSQL_DATABASE`，分别在 `user_db_migration_check`、`book_db_migration_check`、`borrow_db_migration_check` 执行标准 `manage.py migrate --noinput`，检查迁移计划为空，再执行一次验证可重复性。服务 `.env` 不修改。
5. 四个标准 `manage.py runserver 127.0.0.1:<端口> --noreload` 同时启动，真实请求 `/health/live`，确认 HTTP 200 和对应服务名称。
6. 停止测试 Django 进程，保留 MySQL；日志位于 Git 忽略的 `tmp/stage2-runserver/`。

阶段 1 要求自定义用户模型在首次迁移前确定，阶段 2 不开发用户模型。因此实际开发库保持为空，首次业务迁移留到所属业务阶段，**不能直接在 `user_db` 执行默认认证迁移**。三个验证库只验证当前 Django 内置 `auth/contenttypes` 的 14 条迁移能力；不验证尚未实现的业务模型。标准启动出现 14 条未迁移提示是预期状态。统计服务使用 Django dummy backend 表达无业务库，它不迁移，也不是 SQLite。

自定义用户模型首次迁移要求见 [Django 官方文档](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#using-a-custom-user-model-when-starting-a-project)。

## 停止与已有卷注意事项

```powershell
docker compose stop mysql
# 再次启动，保留原有数据：
docker compose up -d --wait --wait-timeout 120 mysql
```

初始化脚本仅在空数据目录首次启动时自动执行，已有卷不会因 `.env` 改动重新创建账号或修改密码，见 [MySQL 官方镜像说明](https://hub.docker.com/_/mysql)。后续修改密码需显式更新已有 MySQL 账号和相应本地配置；不要通过删除已有数据卷来处理认证错误。

本次曾遇到 Windows 挂载脚本以可执行方式运行，调用入口函数不可用，导致建库未执行。已改用直接 MySQL socket 客户端并补执行初始化，保留开发卷；另用独立空卷验证修复后的首次初始化。脚本兼容被 source 和直接执行两种入口方式。
