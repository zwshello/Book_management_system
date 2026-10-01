# 阶段 4：book_db 数据库实现

MySQL 8.4，一个实例中仍按服务分库。book-service 使用 book_app，只访问 book_db（测试另用 book_db_test）；用户授权通过 REST，不建立跨库 FK 或同步用户记录。

| 表 | 字段与约束 |
| --- | --- |
| categories | UUID id；name(100)、normalized_name(100, unique)、description、created_at、updated_at；名称规范化后唯一 |
| books | UUID id；title/author(200)、isbn(13, unique)、category_id FK、publisher(200)、published_date、description、total_copies、available_copies、status、created_at、updated_at、archived_at |
| stock_operations | UUID id；operation_key(UUID, unique)、borrow_id(UUID)、book_id FK、kind、result(JSON)、created_at；borrow_id+book_id+kind 唯一 |

books 保持阶段 1 命名。ISBN-10 输入校验后转为 ISBN-13，避免等价表示重复；ISBN 在归档后仍保留唯一性。分类外键 PROTECT，归档图书仍保留分类关系。归档时间与状态受一致性 CHECK 保护。库存非负并满足 available_copies<=total_copies，MySQL 数据库约束与 Serializer 校验同时生效。category+status 有组合索引，书名/作者模糊查询使用 ORM LIKE。

借阅 ID 在库存日志中只是不可变 UUID，无跨库外键；阶段 5 借阅服务负责实际记录。stock_operations 保存成功或业务失败结果，重复 key 返回原快照；库存行锁保证最后一册只成功预留一次，事务中同时更新库存并保存记录。

库存调整：原占用数=total_copies-available_copies；新总量不得低于占用数，新可借量=新总量-占用数。不能通过普通资料 PATCH 修改库存。初始可借量可以小于总量，表示已有不可用册数；内部释放只认可本系统记录的成功预留，不能凭空增加可借量。

Book/Category 不物理删除历史图书；分类无任何图书引用才删除，有引用时先迁移图书分类。图书归档允许已有预留释放，禁止新预留。

catalog/0001_initial 已实际应用到最初为空的 book_db；重复 migrate 无待执行项。Django 标准 auth/contenttypes 技术表仍由独立项目框架迁移创建，其中 auth_user 不用于业务身份、没有同步用户数据；用户身份仅由 JWT 和 user-service API 提供。

单元与并发测试使用独立 book_db_test，HTTP 集成验证还用 user_db_test。脚本显式检查测试库不同于实际开发库，只清理本轮创建的 UUID/标记对应数据。没有给 book_app user_db 权限，没有使用 SQLite。
