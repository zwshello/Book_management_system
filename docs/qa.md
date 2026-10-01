# 课程答辩问答

以下答案针对**当前已运行的课程版本**。可结合 [架构图](architecture.md)、[API 文档](api.md) 和 [测试报告](test-report.md) 现场说明。

1. **什么是微服务？为什么拆分？** 微服务按业务能力拆为可独立启动、部署和维护的服务，通过网络接口协作。本项目把身份、书目库存、借还协调、统计聚合分开，使每个服务拥有自己的模型、迁移和权限边界。
2. **四个服务分别负责什么？** user-service 负责账户、角色与 JWT；book-service 负责分类、书目和库存真值；borrow-service 负责借阅记录与跨服务借还流程；statistics-service 通过三个业务服务的汇总 API 返回五项统计。
3. **RESTful 是什么？** 用资源 URL 与 HTTP 方法表达操作，例如 `GET /api/v1/books` 查询、`POST` 创建、`PATCH /api/v1/books/{id}` 修改、`DELETE` 归档。接口使用合理的 200/201/204、400/401/403/404/409/503 状态码。
4. **JSON 有什么作用？** 它是浏览器与服务、服务与服务之间的结构化请求/响应格式。字段、错误码和分页结构可被前端与其他服务解析，不依赖页面 HTML。
5. **JWT 怎么工作？** 用户在 user-service 登录后获得 RS256 签名的 access/refresh。浏览器请求带 Bearer access；其他服务用公钥验证签名和声明。管理员敏感操作还向 user-service 核对当前角色及账户状态，以防旧令牌保留已撤销的权限。
6. **为什么权限必须在后端校验？** 前端按钮和路由可以被绕过；任何人都能直接构造 HTTP 请求。后端必须对每次请求做认证与授权。本项目普通用户直调管理员接口返回 403。
7. **MySQL 在项目中怎么使用？** 一个 MySQL 8.4 容器持久化三个逻辑库：`user_db`、`book_db`、`borrow_db`；各服务使用专用账户和独立 Django migration。statistics-service 没有业务库。
8. **为什么不能跨服务直接访问数据库？** 直接读写他人表会绕过所有者的校验、状态和并发规则，使模式变更互相牵连。跨服务只保存 UUID 和必要快照，经受保护的 REST/JSON 接口读写。
9. **borrow-service 如何访问用户和图书数据？** 它用环境变量指定的 `USER_SERVICE_URL`、`BOOK_SERVICE_URL`，携带服务凭据和用户 access。先核验用户资格，再查询图书可借性，然后调用 book-service 的原子库存预留/释放 API。
10. **库存扣了但借阅记录失败怎么办？** 借还使用持久化状态与唯一操作号。网络结果不明时查询同一库存操作结果，待核对记录可由 `reconcile_borrows` 命令恢复；明确失败时执行受控补偿释放。课程项目未引入复杂分布式事务或消息平台。
11. **statistics-service 怎么得到数据？** 它分别调用 user、book、borrow 的受保护汇总端点，业务服务在各自数据库执行聚合；statistics-service 拼出五个数字和 ECharts 图表数据。上游必要服务失败返回 503，不返回假零值。
12. **五项统计如何计数？** 用户总数为未归档用户；图书总数为在架书目；可借数量按在架书的可借册数；已借册数计 `ACTIVE` 与 `RETURN_PENDING`；当前借阅数只计 `ACTIVE`。详见 [统计 API](api.md#statistics-service)。
13. **Docker 是什么？Docker Compose 是什么？** Docker 用镜像运行隔离容器；Compose 用一个配置文件描述七个服务、网络、健康检查、依赖、环境变量和 MySQL volume，并用命令统一构建、启动、查看状态。
14. **容器之间为什么不能用 localhost？** 容器里的 `localhost` 只指向该容器。borrow-service 要找 book-service，必须用 Compose 网络中的 `book-service:8002`，地址由环境变量注入。
15. **Gateway 有什么作用？** Nginx 提供一个浏览器入口，转发 `/api/v1/*` 到对应服务并把其余请求交给 Vue 静态站点。浏览器无需记住多个后端端口；内部接口没有通过网关向浏览器暴露。
16. **为什么用户与图书的 DELETE 不物理删除？** 借阅历史需要保持原 UUID 和展示快照，软归档可阻止新登录/新借阅而不破坏历史。分类若仍被图书引用则拒绝删除；借阅终态记录也只允许管理员归档。
17. **当前为什么没有 Redis、Prometheus/Grafana、Kubernetes、Istio？** 用户调整了当前课程版本，只验收必做的业务、微服务通信与 Docker Compose。缓存、运行监控、集群编排和服务网格是明确暂缓的扩展；当前统计是业务统计，不等同于 Prometheus 监控。
18. **以后怎么扩展？** Redis 可缓存可失效的查询结果，但 MySQL 仍是库存真值；Prometheus/Grafana 可采集运行指标；Kubernetes 可部署健康检查、扩缩容与持久卷；Istio 需在 Kubernetes 之上评估流量治理。每项都需单独设计、配置与实际验证，不能把空目录当作已部署能力。
19. **系统有哪些课程级限制？** 单 MySQL 实例是基础设施单点；五项统计为同步实时聚合，上游故障会返回 503；借还的未知结果需要同操作号核对/恢复；当前无高可用或集群自动恢复。前端大 chunk 有构建提示，但构建和业务测试通过。
20. **怎么证明项目真的可运行？** 展示七容器 healthy、浏览器完整借还与统计、普通用户 API 403、MySQL volume、140 项后端测试和 `npm run build` 结果；详见 [验收追踪](acceptance-checklist.md)。
