# 最终状态报告（课程必做项版本）

日期：2026-10-01。本文以当前代码、阶段 14 测试记录和阶段 15 复验为准；各阶段历史设计见 `phase-*`，如有范围差异，以本文、[当前需求](requirements.md)和实际代码为准。

## 1. 已完成功能

- 用户注册、登录、JWT 刷新与登出、本人资料、管理员用户管理和查询。
- 分类与图书管理；基础、条件、复合、模糊查询，分页和排序；ISBN、库存等后端校验。
- 借书、还书、本人借阅查询与管理员查询。借还经 REST/JSON 调用业务服务，并保留操作号与待处理状态以应对部分失败。
- 管理员业务统计：用户总数、图书书目数、可借册数、已借册数、当前借阅数。前端概览卡片和 ECharts 展示真实 API 数据。
- 普通用户与管理员界面和后端权限边界；重要删除或归档操作使用 Element Plus 二次确认。

## 2. 已完成微服务与调用关系

| 服务 | 数据所有权与职责 | 主要调用 |
| --- | --- | --- |
| user-service | `user_db`；用户、角色、账户状态、认证 | 提供用户授权、借阅资格、汇总接口 |
| book-service | `book_db`；分类、书目、库存 | 提供书目、库存预留/释放、汇总接口；授权时核验用户服务 |
| borrow-service | `borrow_db`；借阅记录与借还协调 | 调用 user-service 和 book-service 的受保护 REST/JSON 接口 |
| statistics-service | 无业务数据库；只聚合五项数据 | 调用三个业务服务的受保护汇总接口 |

同一个 MySQL 8.4 容器承载三个独立逻辑库与专用账号。服务不跨库读取别人的内部表，也不使用跨服务外键。系统架构、模型与 API 见[架构](architecture.md)、[数据库](database.md)、[接口](api.md)。

## 3. 前端与 Docker

- 前端使用 HTML、CSS、JavaScript/TypeScript、Vue 3、Vue Router、Pinia、Axios、Element Plus、ECharts；按角色显示菜单，路由守卫和 Axios 拦截器处理登录状态。授权最终由后端执行。
- Docker Compose 启动 frontend、gateway、四个 Django 服务和 mysql，共七个容器。Nginx gateway 为统一入口，内部通过 Compose 服务名通信，MySQL 使用持久化 volume。
- 当前本机未提交 `.env` 把网关映射到 `127.0.0.1:8088`；[`.env.example`](../.env.example) 默认端口为 8080。实际演示请以 `docker compose ps` 为准。

## 4. 阶段 15 复验结果

| 检查 | 实际结果 |
| --- | --- |
| 前端 `npm run build`，含 `vue-tsc --noEmit` | 通过；Vite 有大于 500 kB 的 chunk 提示 |
| 四个 Django `manage.py check` | 全部通过，0 issues |
| user/book/borrow `migrate --check` | 全部通过，迁移已应用 |
| user/book/borrow `makemigrations --check --dry-run` | 全部通过，无遗漏迁移 |
| Django tests | user 56/56、book 56/56、borrow 22/22、statistics 6/6，合计 **140/140** |
| `docker compose config --quiet`、`docker compose build --quiet`、`docker compose up --build -d --wait` | 全部通过 |
| `docker compose ps` | 七个核心容器均运行且 healthy |
| `scripts/verify_phase10_compose.py`，经 `127.0.0.1:8088` 网关 | 管理员、普通用户、查询、借还、统计、输入校验、权限拒绝和临时数据清理全部通过 |

阶段 14 还实际检查了浏览器页面、角色菜单、删除确认与取消、Dashboard ECharts 展示，记录见[完整测试报告](test-report.md)。阶段 15 的网关业务脚本验证后端数据和 HTTP 流程，未重新进行逐页浏览器截图验收。[项目截图目录](screenshots/README.md)目前只有收集说明，正式截图仍需在演示前采集。

## 5. 课程必做项覆盖

[验收追踪表](acceptance-checklist.md)逐项对应 HTML/CSS/JavaScript/TypeScript/Vue、Django/MySQL、RESTful API/JSON、微服务边界、统一入口、角色权限、CRUD、输入校验、二次确认、各类查询、分页、五项业务统计、Docker/Compose 和多容器联动，并给出现场演示步骤。当前复验未发现阻断课程必做流程的问题。

## 6. 当前未实现选做项

Redis、Prometheus、Grafana、Kubernetes、Istio 均为**当前课程版本未纳入实现范围的扩展功能**，没有部署或相关可运行配置。业务统计不等于 Prometheus/Grafana 运行监控。

## 7. 已知问题与演示注意事项

- 前端构建成功，但 Vite 对超过 500 kB 的 chunk 给出性能提示；课程功能无阻断，后续可优化拆包。
- 网关 `/gateway/health` 只表示网关进程可用；演示时仍须结合 `docker compose ps` 和实际业务流程检查上游服务。
- 借还发生网络结果不明时可能保留待处理记录；可使用 `reconcile_borrows` 人工核对，流程见[借阅设计](phase-1/borrow-workflow.md)。当前没有自动后台调度。
- 首次演示前应准备未提交的 `.env`、管理员账户、可借图书和普通用户；确认本机端口与网关地址，运行 `docker compose up --build -d --wait`。不要执行 `docker compose down -v`，否则会删除 MySQL 数据卷。
- 项目截图尚未采集；[截图说明](screenshots/README.md)明确了存放位置，不把占位文件当作实际截图。

## 8. 建议重点理解的代码

| 主题 | 入口代码 |
| --- | --- |
| 用户模型、JWT 和权限 | `services/user-service/accounts/models.py`、`views.py`、`internal.py` |
| 图书库存与内部接口 | `services/book-service/catalog/stock.py`、`internal_views.py` |
| 借还协调、补偿与幂等 | `services/borrow-service/borrowing/workflow.py`、`clients.py`、`management/commands/reconcile_borrows.py` |
| 五项统计聚合 | `services/statistics-service/analytics/clients.py`、`views.py` |
| 前端鉴权、路由与 API | `frontend/src/stores/auth.ts`、`router/index.ts`、`api/client.ts` |
| 统一入口与容器联动 | `gateway/nginx.conf`、`docker-compose.yml` |

## 9. 老师可能提问的内容

重点准备服务边界与拆分理由、REST/JSON、JWT 和后端授权、三个 MySQL 逻辑库的数据所有权、借还调用链及部分失败处理、统计为何使用汇总 API、Nginx 网关、容器 DNS 与 `localhost` 的区别、Docker Compose 的健康检查和持久化。简答见[答辩问答](qa.md)，现场顺序见[演示指南](demo-guide.md)。

## 10. Git 与交付

`.env`、本地密钥、依赖目录和构建产物被 `.gitignore` 排除；`.env.example` 仅有示例占位值。阶段 15 已检查暂存文件清单、`git diff --cached --check` 和密钥模式；首次提交只包含项目源码、文档及示例配置。交付时仍请以 `git status` 复核工作区。
