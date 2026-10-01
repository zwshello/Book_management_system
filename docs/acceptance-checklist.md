# 课程必做项验收追踪表

本表按当前真实实现映射“验收要求 → 功能 → 微服务 → 前端页面 → 数据库 → 技术 → 现场演示”。当前测试证据见 [test-report.md](test-report.md)；演示顺序见 [demo-guide.md](demo-guide.md)。`user-service`、`book-service`、`borrow-service` 分别只拥有 `user_db`、`book_db`、`borrow_db`，统计服务无业务库。

| 验收要求 | 对应系统功能/API | 对应微服务 | 对应前端页面 | 对应数据库 | 对应技术 | 现场演示与证据 |
| --- | --- | --- | --- | --- | --- | --- |
| HTML | 单页应用入口与语义化表单/表格 | frontend | 登录、列表、详情、Dashboard | — | `index.html`、Vue 模板 | 打开系统与页面源代码 |
| CSS | 布局、角色菜单、表单及统计卡片样式 | frontend | 全站 | — | `src/style.css`、Element Plus | 切换登录和管理页观察布局 |
| JavaScript | 浏览器交互与 API 请求 | frontend | 全站 | — | TypeScript 经 Vite 编译为 JavaScript | 展示 `npm run build` 的 JS 资源 |
| TypeScript | API、模型、路由与组件类型 | frontend | 全站 | — | Vue `<script setup lang="ts">`、`vue-tsc` | 展示构建通过 |
| Vue 3 | 前端组件、响应式页面 | frontend | 全站 | — | Composition API、Vue Router、Pinia | 现场导航与数据刷新 |
| Django / DRF | 独立 REST 服务与后端校验 | 四个 Django 服务 | 由 gateway 接入 | 三库 | Python、Django、DRF | `docker compose ps`，调用 API |
| MySQL | 用户、书目和借阅持久化 | user/book/borrow | 对应业务页面 | `user_db` / `book_db` / `borrow_db` | MySQL 8.4、ORM、migration | 展示三个逻辑库和容器 volume |
| RESTful API | GET/POST/PATCH/DELETE 路由与状态码 | 四服务 | API 层集中调用 | 各自库 | DRF、Nginx 路由 | 展示 [api.md](api.md) 与成功/403 响应 |
| JSON | 浏览器与服务间请求/响应 | 四服务 | 所有动态页面 | 各自库 | `Content-Type: application/json` | 浏览器网络请求或业务脚本输出 |
| 微服务架构 | 独立项目、独立数据库归属、内部服务调用 | 四服务 | 系统整体 | 三库 | REST/JSON、服务凭据 | 展示四容器与 [架构图](architecture.md) |
| 统一访问入口 | `/api/v1/*` 分流和 Vue 路由回退 | gateway + 四服务 | 全站 | — | Nginx | 浏览器只访问一个端口 |
| 普通用户/管理员权限 | 角色路由、菜单和后端实时授权 | user；book/borrow/statistics 执行授权 | 双角色菜单及管理页 | `user_db` | RS256 JWT、DRF permission、内部身份核验 | 普通用户直调管理员 API 得 403 |
| 用户 CRUD | 管理员创建、列表/详情、编辑、归档 | user-service | 用户管理 | `user_db.users` | DRF、ORM | 管理员新建/修改/归档临时用户 |
| 分类 CRUD | 创建、查询、修改、删除 | book-service | 分类管理 | `book_db.categories` | DRF、ORM | 新建和修改分类；无引用时确认删除 |
| 图书 CRUD | 创建、列表/详情、编辑、归档 | book-service | 图书管理、图书查询/详情 | `book_db.books` | DRF、ORM | 新增、查询、修改、归档临时图书 |
| 借还 | 借书、本人记录、还书、管理员全站记录 | borrow-service 协调 user/book | 我的借阅、借阅管理 | `borrow_db.borrow_records`；book 库库存 | REST/JSON、幂等操作号 | 普通用户借书→库存减少→还书→库存恢复 |
| 输入合法性检查 | 用户名/邮箱/密码、ISBN、库存、状态、UUID/查询参数校验 | user/book/borrow | Element Plus 表单 | 三库约束 | DRF serializer、Django/ORM 约束 | 提交空值、非法 ISBN、负库存；看前后端拒绝 |
| 删除二次确认 | 取消不请求后端，确认后调用归档/删除 API | user/book | 用户、图书、分类管理 | 相应库 | `ElMessageBox.confirm` | 对三种对象分别展示弹窗、取消和确认 |
| 基础查询 | 用户、分类、图书与借阅列表/详情 | user/book/borrow | 管理页、查询页 | 三库 | GET API、ORM | 打开列表和详情 |
| 条件查询 | 角色、状态、分类、可借性、日期等过滤 | user/book/borrow | 用户、图书、借阅管理 | 三库 | DRF query serializer | 选择分类和状态查询 |
| 复合查询 | 多条件按 AND 组合 | user/book/borrow | 图书查询、管理筛选 | 三库 | ORM filter | 书名包含词 + 分类 + 可借状态 |
| 模糊查询 | `username_contains`、书名/作者包含搜索 | user/book | 用户管理、图书查询 | `user_db` / `book_db` | ORM `icontains` | 输入部分用户名、书名或作者 |
| 分页与排序 | `page`、`page_size`、`ordering` | user/book/borrow | 各列表页 | 三库 | API 分页、稳定排序 | 小页长切换页码与排序 |
| 基础统计 | 用户总数、图书书目数、可借册数、已借册数、当前借阅数 | statistics-service 汇总三服务 | 管理 Dashboard、统计分析 | 无统计库；读取三个聚合 API | REST/JSON、ECharts | 借前/借后刷新五项数字和柱状图 |
| Docker | 各应用镜像和 MySQL 容器 | 七组件 | 全站 | MySQL volume | Dockerfile、Docker Desktop | `docker compose build` |
| Docker Compose | 健康检查、依赖、网络、持久化 | 七组件 | 全站 | `library-dev_mysql-data` | `docker-compose.yml` | `docker compose up -d --wait`、`ps` |
| 多容器联动 | borrow→user/book、stats→三服务、gateway→各服务 | 四服务 + gateway | 借还与统计页 | 三库严格隔离 | Docker DNS 服务名、REST/JSON | 完整借还和统计流程，同时展示七容器 healthy |

## 当前范围判定

Redis、Prometheus、Grafana、Kubernetes、Istio 均是**当前课程版本未纳入实现范围的扩展功能**，此表没有将它们记作已完成项。未来设计可以另行评估，不影响当前五项业务统计与 Docker Compose 演示。Git 交付状态与密钥检查见 [最终状态](final-status.md)。
