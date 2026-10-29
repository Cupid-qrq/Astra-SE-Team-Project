# 业务服务与Worker

B建立公共工程，A/B按[架构模块表](../docs/02-architecture.md)实现各自业务。P0建立pyproject、uv锁文件、FastAPI、SQLAlchemy、Alembic、pytest、格式与类型检查。

```text
app/api/                 路由装配与统一协议
app/modules/             identity、courses、problems等业务模块
app/shared/              事务、时钟、ID、错误与公共端口
app/adapters/            Judge0、模型和外部基础设施适配
app/workers/             评测、提示、通知、恢复与维护进程
migrations/              Alembic迁移（B协调单head）
tests/unit/              领域与应用用例
tests/integration/       真实PostgreSQL与适配器集成
```

所有进程共用规则实现；Worker不能绕过授权和事务直接修改成绩。A 已在 `app/modules` 实现身份/课程、题目、作业和固定帮助基础；独立 API、PostgreSQL 迁移和检查方法见 [A线接入说明](a_line/README.md)。B 的共享事务/时钟基础已独立实现；正式总入口、A存储适配、Worker 和总迁移仍待集成；独立验证入口不作为生产入口。

## B 共享层 S1

`server/pyproject.toml` 与 `uv.lock` 提供独立锁定环境（Python 3.12—3.13、uv 0.13.5）。本阶段不启动HTTP服务、不创建业务表、不运行学生程序。

- `create_database_engine(url)` 只接受 PostgreSQL psycopg URL，默认 READ COMMITTED、UTC、有界连接池与5秒连接超时；配置错误不回显URL。SQL参数隐藏，调用方仍须禁止记录连接串和驱动异常中的敏感内容。
- `with UnitOfWork(engine) as connection` 将同一个 Connection 传给参与模块的 Repository/Effects；成功提交，异常（包括提交失败）回滚并归还连接。一个UoW只能进入一次；参与服务不得自行 commit/rollback。提交结果不确定时不能自动重放业务写入。
- `DatabaseClock(connection).now()` 使用数据库实际时钟并归一化到 UTC 毫秒；受理代码须在获得规定锁之后读取，不能先取时刻再等锁。

从仓库根目录执行（连接值通过本地环境配置注入，勿将真实值写入Git）：

```powershell
uv sync --locked --project server
# 设置 ASTRA_TEST_DATABASE_URL，指向专用 postgresql+psycopg 的 *_test 数据库
pwsh -NoProfile -File tools/check_server.ps1
# 完整回归还需要 A 独立测试配置 ASTRA_A_DATABASE_URL 和前端依赖/浏览器
python tools/check_runtime.py
```

缺数据库配置会失败，不跳过或改用SQLite。共享层测试用随机 `b_shared_` schema，只清理自己创建的schema。A套件使用不同前缀，CI可复用一个专用测试数据库。生产库不参与测试。Windows通过WSL本机转发连接时，需保持WSL会话存活并确认数据库正在监听；退出WSL会话后应重新核验连接。

S1验证共享库本身。正式单head迁移、A模块改用该UoW、生产HTTP与跨线完整验收属于后续阶段；不能用本阶段测试计数宣称已接通A业务。
