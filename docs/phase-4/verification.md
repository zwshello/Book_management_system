# 阶段 4：验证记录

日期：2026-09-30。范围为分类、书目、图书侧库存接口，以及必要的用户内部授权；未开发借阅服务业务。

## 实际执行结果

- book_db 首迁移前 SHOW TABLES 为 0；生成 catalog/0001_initial 并完成 MySQL auth/contenttypes/catalog 全部迁移，含库存/状态/归档 CHECK 与唯一约束。
- book-service 单元/事务测试：**52 项通过，约 2.443 秒**，使用 book_db_test。
- user-service 回归：**49 项通过，约 12.001 秒**，原 43 项加 6 项内部授权测试，使用 user_db_test。
- 真实 user-service :8001 与 book-service :8002 HTTP 集成通过，使用独立测试库，测试后进程与本轮数据清理，开发 MySQL 保持运行。
- 最终 user-service 与 book-service 的 manage.py check 均为 0 issues；两者 makemigrations --check --dry-run 均为 No changes detected。
- book-service 再次 migrate --noinput 返回 No migrations to apply，验证已有库迁移状态一致；pip check 返回 No broken requirements found。
- 根目录及两个服务的真实 .env 均已被 Git 忽略；图书服务未配置 JWT 私钥。README、总体 API 合同、用户内部授权说明与图书数据库文档已同步。

## 用户要求对应测试

| 要求 | CatalogApiTests 中的测试 |
| --- | --- |
| 管理员创建分类 | test_admin_creates_category |
| 管理员创建图书 | test_admin_creates_book |
| 普通用户不能新增 | test_ordinary_user_cannot_write |
| 修改图书 | test_modify_book |
| 删除图书 | test_archive_book |
| 查询详情 | test_detail_query |
| title 模糊查询 | test_title_fuzzy_query |
| author 查询 | test_author_fuzzy_and_exact_query |
| ISBN 查询 | test_isbn_query_and_isbn10_conversion |
| 分类过滤 | test_category_filter |
| status 查询 | test_status_query |
| 多条件组合 | test_combined_query |
| 分页 | test_pagination_and_sorting |
| 非法 ISBN | test_illegal_isbn |
| 重复 ISBN | test_duplicate_isbn_and_alias |
| 负库存 | test_negative_stock |
| 可借数大于总数 | test_available_exceeds_total |
| 无权限访问 | test_unauthenticated_access / test_ordinary_user_cannot_write |

另覆盖分类 CRUD/规范化重复/引用保护、状态归档与恢复、普通用户归档访问保护、必填字段/日期/分类存在性/未知字段、库存调整占用保护、数据库库存约束、JWT 声明/过期、陈旧管理员角色、依赖失败、查询参数/错误结构。

StockApiTests 验证预留/释放、重放不变更、原失败持久化、未预留不能释放、同 key 参数冲突、同借阅换 key 冲突、归档仍可释放、按操作号恢复核对、必填幂等编号、拒绝用户 JWT 和无服务身份。真实 MySQL 两线程争最后一册：一个 200、一个 409，最终库存 0，操作结果各一条。

UserClientTests 验证依赖不可用、非法响应、用户 token 401 和服务身份失配 503。用户服务的 6 项新增测试确认当前角色、拒绝 JWT 替代服务身份、缺失/错误用户 token、停用、改密码、主体不一致。

## 真实 HTTP 证据

scripts/verify_phase4_http.py 实际验证：用户登录 → 管理员创建分类/图书（201）→ 普通用户查询（200）与写入拒绝（403）→ title+分类+可借组合查询 → 总量调整 → 独立服务身份预留并重放 → 用户 JWT 调内部接口 401 → 图书归档 204/公开详情 404 → 原借阅库存释放 → 状态恢复 → 管理员降级后旧 token 写入 403 → 停用后 401 → 用户服务停机写入 503，书名保持原值，普通只读查询仍可进行。

HTTP 脚本没有使用模拟用户授权返回；公钥、本地真实服务凭据与 REST/JSON 实际联动。日志在忽略的 tmp/phase4-http/。测试业务数据仅存在隔离测试库，完成后定向清理。

## 修复过程

初始启动出现认证模块导入错误处理模块、错误处理模块提前导入 DRF views 的循环依赖；改为异常处理函数内加载 DRF handler 后检查通过。首轮归档释放测试保存旧模型实例，覆盖预留后的库存；修正测试刷新实例并仅保存归档字段后全部通过，未删除任何库存校验。

Windows 开发工具一度出现高并发进程/DLL 加载问题；格式化改用单 worker，Docker 命令重新执行成功。没有改变业务验证方式或用 SQLite 替代 MySQL。

## 当前边界及阶段 5 前提

没有已知阻塞问题。阶段 5 必须实现借阅记录、用户资格、并发借阅上限、状态转换与部分失败恢复；图书侧库存接口完成不代表借还业务已完成。复用相同 borrow_id/operation_key，不按超时猜测结果，不换 key 自动重试，不跨库读 users/books。

BORROW_SERVICE_TOKEN 当时配置在 book-service 本地环境中，阶段 5 再安全配置给 borrow-service；它不是用户 JWT。普通图书只读接口本地验签，敏感管理及归档列表实时核对当前权限。前端确认已在阶段 7 实现；阶段 9 用户暂缓缓存；网关和完整部署仍属后续阶段。本记录保留阶段 4 的测试历史。
