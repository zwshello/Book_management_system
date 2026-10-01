# 阶段 2：基础工程验证记录

> 本页记录阶段 2 当时的状态。阶段 10 已实现完整核心 Compose 部署；当前启动方式与验证结果见根目录 README 和 `docs/phase-10/verification.md`。

验证日期：2026-09-30。范围仅限工程结构、依赖、配置、构建、开发 MySQL、内置迁移及存活接口，不代表业务功能完成。

## 环境与版本

- Windows；Node.js 24.21.0，npm 11.19.0，Python 3.11.5，Git 2.54.0。
- 前端 `npm install` 成功，生成 `frontend/package-lock.json`；`npm run build` 类型检查和 Vite 构建成功（Vite 7.3.6）。
- Python 虚拟环境 `.venv/` 安装 Django 5.2.17、Django REST Framework 3.16.1、python-dotenv 1.2.3、mysqlclient 2.3.0、Uvicorn 0.54.0。`pip check` 报告无损坏依赖；四份 `requirements.txt` 的每条版本约束均由已安装版本满足。
- Docker Client/Engine 29.8.1、Docker Desktop 4.93.0、Compose v5.5.1；`mysql:8.4` 实际运行 MySQL 8.4.11。

## 实际执行的检查

| 检查 | 结果 |
| --- | --- |
| 前端 `npm run build` | 通过；包含 `vue-tsc --noEmit` 与 Vite 生产构建 |
| 前端 `npm run dev` | 在 `127.0.0.1:5173` 启动；GET `/` 返回 HTTP 200 和应用入口 HTML；验证后已停止 |
| 四服务 `manage.py check` | 全部通过，均报告 0 issues |
| 四服务 ASGI 启动 | 各服务的 `start.py` 读取独立端口配置并通过 Uvicorn 在 8001、8002、8003、8004 启动；各自 GET `/health/live` 返回 HTTP 200 及正确服务名；验证后已停止 |
| 配置加载 | 四服务识别各自服务名；前三个配置为 MySQL 的 `user_db`、`book_db`、`borrow_db`，统计服务为无业务库配置 |
| 本地 `.env` 文件加载 | 对 user-service 使用一次仅含测试值的临时 `.env`，`manage.py check` 通过且读取了 Debug、库名和测试密钥；测试后已删除该文件 |
| 端口 | 5173、8001–8004 启动时无冲突；验证后进程停止 |
| Git | 已在项目根目录初始化 `main` 分支；`.env`、虚拟环境、`node_modules` 与构建产物被忽略；`.env.example` 和 `package-lock.json` 可纳入版本管理 |

## Docker 安装后的补充验证

首次基础验证时缺少 Docker/MySQL，标准 `runserver` 因连接被拒绝退出。用户安装 Docker Desktop 后，现已完成以下补充验证，原数据库环境阻塞已解除。

| 检查 | 实际结果 |
| --- | --- |
| Docker 引擎及端口 | Client/Server 正常；启动前 3306 和 8001–8004 空闲 |
| 配置生成 | `scripts/setup_dev_env.py` 创建根目录及四份服务 `.env`，随机密码/密钥不输出；再次执行不覆盖文件 |
| Compose 配置 | `docker compose config --quiet` 成功；只定义 mysql 服务 |
| MySQL 容器 | `docker compose up -d --wait --wait-timeout 120 mysql` 成功；`library-dev-mysql-1` 为 healthy，绑定 `127.0.0.1:3306` |
| Django 数据库连接 | user/book/borrow 均通过 Django MySQL backend 执行查询，返回各自库名、8.4.11、1；三个实际开发库当前表数均为 0 |
| 账号隔离 | 三个服务尝试访问另一服务库均收到 1044，权限隔离通过 |
| user-service migration | 在 `user_db_migration_check` 的 14 条 `auth/contenttypes` 内置迁移全部成功；重复执行无待迁移项 |
| book-service migration | 在 `book_db_migration_check` 同样通过 14 条迁移及重复执行检查 |
| borrow-service migration | 在 `borrow_db_migration_check` 同样通过 14 条迁移及重复执行检查 |
| statistics-service migration | 不适用；无业务库，保留 dummy backend，未改用 SQLite |
| 四服务 `manage.py check` | 加载真实本地配置再次执行，全部报告 0 issues |
| 四服务标准 `runserver` | 使用实际开发库在 8001/8002/8003/8004 同时启动；不使用 `--skip-checks`，只用 `--noreload` 避免测试子进程重载；四个存活接口均 HTTP 200 且服务名正确 |
| 空卷首次初始化 | 独立临时项目 `library-dev-initcheck` 在 3307 从空卷启动为 healthy；三个新建账号均可连接各自库；核对临时卷身份后已清理该测试项目，开发卷保留 |
| MySQL 驱动 | mysqlclient 2.3.0 已满足前三份 requirements，MySQL 8.4 认证与迁移实际成功；不需额外驱动或改写依赖 |
| 秘密配置忽略 | 根目录与四个服务 `.env` 均由 `git check-ignore` 确认为忽略；未提交真实密码 |
| 验证后的状态 | 四个测试 Django 进程停止；开发 MySQL 仍为 healthy；标准启动日志保留于忽略的 `tmp/stage2-runserver/` |

首次初始化遇到脚本被 Windows 挂载为可执行文件、无法使用 entrypoint 函数的问题。已定位并修复为直接调用 socket MySQL 客户端；在原开发卷补建库与账号，并通过独立空卷首次启动验证。没有删依赖、跳过配置或切换 SQLite。

可重复验证入口与 PowerShell 命令见 [开发数据库说明](mysql-development.md)。

## 当前限制与下一阶段前提

- 阶段 1 要求自定义用户模型在首次迁移前确定。因此本次迁移只针对服务各自的独立验证库；实际 `user_db` 保持为空，**尚未执行首次用户业务迁移**，避免留下默认 `auth_user` 后再更换模型。三个验证库中的内置认证表不代表最终业务模型。
- 实际 `book_db`、`borrow_db` 也保持为空，业务模型在所属阶段实现。前三个标准服务启动日志中的 14 条未迁移提示是当前预期状态；不通过关闭迁移检查隐藏它。
- 当时已验证数据库环境和标准启动；尚未验证后续阶段的 CRUD、JWT 与完整容器联动。此条仅记录阶段 2 当时的状态；阶段 9 暂缓 Redis，阶段 10 已完成网关与 Compose，阶段 12、13 分别跳过 Kubernetes 与 Istio。
- 根目录 Compose 仅用于开发 MySQL，不能启动完整系统；完整 Docker 部署在阶段 10 实现并验证。
- 阶段 3 开始前确定 user-service 自定义用户模型及首次 migration；JWT 密钥和管理员初始账号后续由本地环境安全注入。已有卷修改 `.env` 不会自动同步数据库密码，需要显式管理账号。借阅上限、自助注册等业务参数按阶段 1 文档在相关实现前确认。
- 本次结束后停止，等待用户明确发送“开始阶段 3”。
