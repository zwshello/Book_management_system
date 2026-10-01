# 阶段 6 验证记录

范围按用户最新要求缩减为五项概览统计。statistics-service 无模型和业务数据库，故本阶段无统计库 migration。user、book、borrow 三个汇总端点只读取各自业务库，未新增模型 migration。

## 验证方式

从项目根目录运行 `scripts/setup_statistics_auth.py`，为四服务配置共用的内部统计凭据，并只向统计服务分发 JWT 公钥。分别运行四个服务的 `manage.py check`、三个业务服务的 `makemigrations --check --dry-run` 和测试；运行 statistics-service 的 `manage.py test analytics`。随后运行 `scripts/verify_phase6_http.py`，它以标准 `runserver` 启动四服务并使用隔离测试库完成真实 HTTP 联调。

真实 HTTP 联调已验证：普通用户请求概览返回 403，管理员返回 200 且五项数值及 ECharts 数组正确；取消的分类、热门、月度、用户排行路径返回 404；book-service 停止后概览返回 503。验证脚本结束时停止四个进程并删除本次测试数据。

2026-09-30 最终回归：user-service 56 项、book-service 55 项、borrow-service 22 项、statistics-service 6 项，合计 139 项测试全部通过。四个 Django 项目的 `manage.py check` 均无问题；三个业务服务的 `makemigrations --check --dry-run` 均提示无模型变更，`migrate --check` 均通过。统计服务没有业务模型与迁移。

## 边界

统计属于请求时聚合，三个业务服务中任一不可用则概览不可用。高流量时可能增加跨服务请求。阶段 9 用户已明确暂缓 Redis，当前版本不缓存概览；若未来另行确认缓存扩展，仍不能把缓存当业务真值。此处保留阶段 6 当时的验证记录；前端图表已在阶段 7 实现并于阶段 8 联调，网关完整路由和容器部署仍属于后续阶段。
