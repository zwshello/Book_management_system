# 阶段 14：完整系统测试报告

日期：2026-10-01。范围为当前课程必做版本。测试数据使用独立的 MySQL 测试库或带 `phase10_` / `phase14ui_` 前缀的临时记录；运行结束已清理这些临时记录。

## 测试环境

| 项目 | 实测环境 |
| --- | --- |
| 主机 | Windows、PowerShell、Docker Desktop |
| Python / Django | Python 3.11.5、Django 5.2.17；`pip check` 无依赖冲突 |
| 前端 | Node.js 24.21.0、npm 11.19.0、Vue 3、TypeScript、Vite |
| 容器 | Docker 29.8.1、Compose v5.5.1；MySQL 8.4、Nginx 网关与静态前端、四个 Django 服务 |
| 入口 | 本机未提交的 `.env` 使用 `GATEWAY_PORT=8088`，测试地址 `http://127.0.0.1:8088/`；`.env.example` 默认 8080 |
| 数据边界 | MySQL 同一实例中的 `user_db`、`book_db`、`borrow_db`；statistics-service 无业务库，通过受保护的 REST/JSON 汇总端点获取数据 |

## 执行结果

| 项目 | 命令或方法 | 结果 |
| --- | --- | --- |
| Python 依赖 | `python --version`、`python -m django --version`、`pip check` | 通过 |
| Django 检查 | 四个容器分别执行 `python manage.py check` | 全部通过，0 issues |
| 迁移一致性 | user、book、borrow 分别执行 `migrate --check` 与 `makemigrations --check --dry-run` | 全部通过，无待生成迁移 |
| 后端测试 | 四个容器内运行各自 Django 测试，使用隔离 MySQL 测试库 | user 56/56、book 56/56、borrow 22/22、statistics 6/6；合计 **140/140** |
| 前端构建 | `npm run build`，包括 `vue-tsc --noEmit` | 通过，2304 个模块完成构建；大于 500 kB 的 chunk 仍有 Vite 提示 |
| Compose | `docker compose config --quiet`、`docker compose build --quiet`、`docker compose up --build -d --wait`、`docker compose ps` | 通过；frontend、gateway、user-service、book-service、borrow-service、statistics-service、mysql 共 7 个容器均 healthy |
| Nginx | 容器内 `nginx -t` | 通过 |
| 容器业务 | `PHASE10_GATEWAY_URL=http://127.0.0.1:8088` 运行 `scripts/verify_phase10_compose.py` | 网关修复前后各通过一次；脚本清理临时数据 |

### 功能与权限覆盖

| 模块 | 实测内容与证据 | 结果 |
| --- | --- | --- |
| 用户 | 注册、登录、RS256 JWT、refresh/登出、当前用户、资料修改、管理员 CRUD/禁用启用、用户名精确/模糊和组合查询、分页、密码哈希、重复用户名/邮箱、非法邮箱/密码/role/ID | Django 测试及容器 HTTP 流程通过 |
| 图书 | 分类 CRUD、引用中分类拒删、图书创建/详情/修改/归档、书名与作者模糊、ISBN 精确、分类与状态过滤、复合查询、分页排序、ISBN 和库存约束、库存保留/释放幂等 | Django 测试及容器 HTTP 流程通过 |
| 借阅 | 正常借还、重复还书、无书/无用户/无库存、未认证、本人私有列表、管理员总列表、跨服务不可用、响应丢失后的同操作号恢复、并发库存与补偿路径 | Django 测试及容器 HTTP 流程通过 |
| 统计 | 用户总数、图书总数、可借册数、已借册数、当前借阅数；上游 503、数据格式和普通用户拒绝 | 6 个服务测试及容器 HTTP 流程通过；浏览器看到与临时数据一致的五张卡片和 ECharts 柱状图 |
| 后端权限 | 普通用户直调用户列表/创建、图书创建/修改/删除、管理员统计 API 均返回 403；未认证返回 401；普通用户读他人借阅记录返回 403 | 容器 HTTP 实测通过，非仅检查菜单 |
| 安全配置 | `.env` 与服务本地 `.env` 被 Git 忽略；`.env.example` 为 `CHANGE_ME` 占位；JWT 密钥和数据库密码从环境变量加载；用户密码通过 Django 哈希；跨服务无数据库直连 | 代码、配置、测试核对通过 |

### 浏览器交互

在 Docker 网关页面实际完成：管理员登录与登出、角色菜单、管理首页和统计图；普通用户登录与登出、仅普通菜单、书名与作者复合模糊查询、图书详情、借书（可借库存 2→1）、我的借阅、还书（记录变为 `RETURNED`）、管理员路由重定向；管理员借阅页看到该记录。

用户、图书、分类的删除操作均先出现 Element Plus 二次确认。对三者点击“取消”后列表记录仍在；对临时用户和图书点击“确认归档”后列表分别更新。对已被图书引用的分类点击“确认删除”，后端拒绝并显示明确错误。分类空名称在前端表单显示必填提示。后端测试和 HTTP 流程另验证非法邮箱、重复 ISBN、负库存、超量库存等错误输入。

前端请求拦截器负责附加 JWT；401 清除会话并转到登录页；403 等后端错误由页面统一错误文本显示。浏览器已实测普通用户无法进入管理员路由，后端 401/403 则由容器 HTTP 实测。失效 JWT 的浏览器跳转未再次单独演示，已有相关代码检查及后端 JWT 测试覆盖。

## 发现的问题与修复

1. 前端顶栏及统计页仍显示早期“阶段 7 / 阶段 6”文案。已改为课程项目和五项基础统计的当前表述；`npm run build` 通过，网关返回的静态入口与本地新构建的资源哈希一致。
2. 单独重建 frontend 容器后，原网关缓存旧容器 IP，页面请求曾断开，而网关自身健康检查仍为通过。已在 `gateway/nginx.conf` 配置 Docker DNS 动态解析并保持原始请求 URI；重建网关后，`nginx -t`、全部业务 HTTP 流程及强制重建 frontend 后的 `/login` 请求均通过。
3. 本地构建曾先受到沙箱读权限和 Node 默认堆大小限制；在正常权限下设置临时 `NODE_OPTIONS=--max-old-space-size=2048` 后通过。Docker 构建缓存占用较多磁盘，清理未使用的构建缓存后重试成功。未修改应用需求或绕过类型检查。

## 尚存问题与验收判断

- 当前仓库 `main` **尚无 Git 提交，项目文件仍未跟踪**。这不影响本次运行结果，但 Git 是课程指定技术栈；最终提交前应检查暂存内容不含本地密钥，并建立可复现的提交记录。
- 前端生产构建仍提示单个 chunk 超过 500 kB；构建与页面运行通过，这是性能优化项。
- 网关 `/gateway/health` 仅证明网关进程存活，不能单独证明所有上游可用；课程演示应同时运行完整业务流程。借还对不确定的跨服务结果保留同操作号与核对机制，运维恢复步骤见阶段 5 文档。
- **Redis、Prometheus、Grafana、Kubernetes、Istio 是“当前课程版本未纳入实现范围的扩展功能”**，不是本报告中的缺陷，未进行安装或测试。

当前必做的系统功能、权限、MySQL 持久化、REST/JSON 协作和 Docker 联动均已通过测试。完成 Git 首次提交并整理最终验收材料后，可进入最终文档整理；本阶段不启动阶段 15。
