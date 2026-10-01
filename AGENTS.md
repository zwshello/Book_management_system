# 项目协作规则

## 目标与技术栈

本项目用于“微服务与云原生技术实践”课程实习验收。保持四个可独立运行、通过 REST/JSON 协作的 Django 微服务，并提供 Vue 3 + TypeScript Web 界面。当前验收版本使用 Django REST Framework、JWT、MySQL、Nginx、Docker/Compose 和 Git。用户在阶段 9 暂缓 Redis、NoSQL 缓存、图书查询缓存与 Dashboard 缓存；阶段 11 跳过 Prometheus/Grafana，阶段 12 跳过 Kubernetes，阶段 13 跳过 Istio。这些组件不属于当前部署或验收范围，后续可经确认作为扩展加入。未经用户同意，不替换当前指定技术栈，也不合并为单体项目。

## 服务边界

- `user-service`：用户、角色、账户状态与认证，独占 `user_db`。
- `book-service`：分类、书目、库存与库存操作，独占 `book_db`。
- `borrow-service`：借阅记录与借还协调，独占 `borrow_db`。
- `statistics-service`：通过 API 汇总统计，不跨服务读取数据库；初期无业务库。

跨服务数据只通过受保护的 REST/JSON API 读取或变更。具体边界、状态与接口见 `docs/phase-1/`。

## 编码与安全

- Python 遵循 PEP 8，变量和函数使用 `snake_case`，类使用 `PascalCase`；TypeScript 明确类型，Vue 使用 Composition API 与 `<script setup lang="ts">`。
- 后端最终校验所有输入和每个请求的权限；前端只承担体验层校验与菜单显示。删除等重要操作先二次确认。
- 密码只保存哈希。真实密码、JWT 私钥、服务令牌不得写入代码或提交仓库；使用环境变量和未提交的本地配置。
- 不跨服务访问表；库存与借阅真值保存在各自 MySQL 业务库，不引入未确认的缓存层；不用未经定义的自动重试执行借还写操作。

## 开发与验证

- 修改前阅读相关代码及文档；每次聚焦一个阶段，不重构无关模块。
- 修改模型后生成并验证 migration；修改 API 后同步更新接口文档；修改启动方式后同步更新 README。
- 每个功能至少验证正常路径、输入错误和权限边界。借还必须验证并发、幂等和部分失败；不能通过删除功能或绕过异常让测试通过。
- 每一阶段以 `docs/phase-1/requirements.md` 的验收标准为准，并记录实际执行的测试结果。不要把规划中的能力描述为已实现。
- 阶段 1 只形成规划文档，不编写业务代码；阶段 2 起按用户确认的顺序推进。
- 当前 Dockerfile 与 Compose 配置必须实际验证；若今后经用户确认实施 Kubernetes 或 Istio，也必须分别实际验证，不得把占位文件称为可部署系统。容器间使用服务名和环境变量通信，不把 `localhost` 写死为容器内部依赖地址。
- 完成一个阶段后停止，等待用户明确指定下一阶段；不得自动进入阶段 3 或后续阶段。
