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

所有进程共用规则实现；Worker不能绕过授权和事务直接修改成绩。A 已在 `app/modules` 实现身份/课程、题目、作业和固定帮助基础；独立 API、PostgreSQL 迁移和检查方法见 [A线接入说明](a_line/README.md)。B已实现共享事务/时钟、A兼容存储适配及正式迁移链；正式HTTP总入口已装配A教学服务，Worker仍待接入；独立验证入口不作为生产入口。

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

## B 正式迁移与存储 S2

设置 `ASTRA_DATABASE_URL` 后，从根目录显式执行：

```powershell
uv sync --locked --project server
uv run --project server alembic -c server/alembic.ini upgrade head
```

正式链为 `b001→b002→b003→b004→b005`，使用 `alembic_version`。前四版是A已提交SQL的逐字节固定副本，第五版引入policy_guard、审计和Outbox；升级不导入当前metadata，也不在应用启动时建表。A的独立链仍用于原验证，不在正式数据库运行。发现 `alembic_version_a` 时正式入口拒绝升级；不自动stamp或猜测既有结构。需要转移A验证数据时另做受审的数据迁移，不在这里原位改版本表。破坏性downgrade关闭。

`app.shared.metadata` 汇总同一个A/B metadata对象，补齐A004已有但原metadata遗漏的帮助作者索引。正式迁移测试对照该对象检查表/列/外键/索引等Alembic支持的差异，并验证A快照字节不变。B业务表尚未进入，预检/成绩/attempt的跨线外键仍待各表落地时补齐。

在 `UnitOfWork` 返回的Connection内构造 `SqlRepository`。需要策略保护的用例首先调用 `guard()`，然后按规范锁课程、作业；它使用数据库单行锁，不复用A验证适配器的全局advisory lock。Repository不负责身份授权，也不自行提交。A应用服务仍承担权限/业务校验。

`rows()` 保持A内部完整集合查询语义；公开列表不得直接用它全量读取后分页。HTTP接入使用 `page(table, limit=1..100, after=主键, **filters)` 等按授权条件构造的查询。当前page支持单主键稳定游标，其参数必须先经API校验；复合主键或更复杂排序需要明确扩展端口。

`TransactionalEffects(repo, request_id)` 绑定同一个Repository，拒绝传入其他事务的Repository。A的课程/账号/题目/作业动作在同一事务写审计与Outbox；摘要只散列，事件不复制任意summary正文。成员变化经A受控端口更新作业revision/grade_epoch，失败随业务一起回滚。Outbox消费、通知收件人和正式成绩协调仍待后续实现。

审计表由触发器禁止UPDATE/DELETE。本阶段没有部署角色或维护账号，正式部署仍需按运行规范限制业务账号为审计INSERT/SELECT；留存清理的维护通路后续单独实现，不以本机测试表owner权限冒充最小权限验收。

本阶段已可在正式schema中直接用A应用服务、B Repository/Effects和共享UoW组合调用。A的独立HTTP host仍保留自己的验证装配；总HTTP装配在S3切换，不能将原A浏览器回归称为B生产HTTP验收。

## B 正式HTTP S3a

正式入口是 `app.main:create_app`，生产不导入a_line验证应用。先显式执行正式迁移，再通过部署环境设置[配置样例](.env.example)中四个必需值；不会自动读取.env。数据库必须为postgresql+psycopg；会话密钥至少32字节、内部健康令牌至少32字节，Origin必须为完整HTTPS来源且不带路径。缺配置启动失败，错误及repr不回显凭据。

从仓库根目录启动：

```powershell
uv sync --locked --project server
uv run --project server uvicorn app.main:create_app --factory --app-dir server --host 127.0.0.1 --port 8000 --no-access-log
```

应用位于HTTPS反向代理后，浏览器与API同源；Cookie使用Secure/HttpOnly/SameSite=Lax。API前缀/api/v1。`GET /health/live`公开；`GET /health/ready`要求X-Readiness-Token，检查正式迁移head后返回就绪状态，不提供数据库细节。应用启动不建表、不创建账号、不种题目、不合成执行证据。管理员初始化、部署最小权限及评测VM另行验收。

每次请求先限制512KiB正文，严格校验JSON语法/重复键/UTF-8，再进入共享UoW；获得policy_guard后解析当前身份，写请求校验Origin/CSRF。响应在提交前按canonical schema验证；Cookie只在提交成功后发送。A的Fault(commit=True)仅用于保存登录失败账本，普通业务错误整体回滚。后台GET与session查询不延长空闲会话。

公开大列表在授权SQL中使用limit+1和稳定主键，游标签名绑定用户、路由和过滤条件；内部rows不截断。测试点/参考程序/运行profile受业务或配置上限约束，允许有界内存分页。运行profile未配置、既有方法所需的预检/成绩协调未接通时返回503；提交前端端口保留显式503占位，未实现的B路由不注册。不以测试合成值响应生产请求。

本阶段消费A契约片段，生产仅注册已实现的38个教学方法；总契约、生成类型来源切换及正式应用浏览器检查在S3b完成。A独立浏览器入口继续保留，不冒称其结果证明正式应用联通。

## B 总契约与正式应用浏览器 S3b

总入口[specs/openapi.yaml](../specs/openapi.yaml)当前包含40个已实现方法（38教学+2健康）和18个未来设计方法；A片段仍独立验证。正式FastAPI导出实际注册路由及契约元数据，检查器对照完整URL/前缀、方法、状态、参数、schema和安全定义。生成客户端从总入口读取。

`tools/check_server.ps1`运行锁定依赖、格式/类型、契约映射、真实数据库全部共享层/HTTP测试及正式应用浏览器。后者复用A的教学流程，显式测试harness使用正式B迁移/UoW/Repository/Effects/create_app，初始化虚构账号和合成教学版本。当前外部执行端口继续不可用；前端端口fake专项单独标识。

浏览器随机schema以独立run marker记录；正常退出与独立teardown均可幂等清理，仅匹配本run和_test库。清理失败使检查失败，marker供定位；不会批量删除其他测试schema。此验证覆盖三个Chromium视口，完整跨浏览器、独立VM及业务闭环另行验收。

正式HTTP将未知内部约束/持久化异常归为503，已知业务冲突由应用Fault返回409。PostgreSQL文本及JSONB的NUL按字段返回422；已明确的bytea源码/测试及散列密码通道保持其原字节语义。

## B 执行契约 S4a

`app.shared.judge.JudgePort`提供单测试点创建、轮询和监督清理端口。租约身份包含attempt/generation/lease_epoch/testcase_order；执行键与请求摘要分离，后续Worker必须持久记录创建状态，不能只靠进程内幂等。当前无生产Worker接入，也不在业务机执行代码。

`RuntimeProfile.from_public`复用A的profile_digest冻结公开snapshot；`ProfileCatalog`按完全一致的摘要允许执行。部署单独登记语言ID，不使用公开演示服务的默认ID。资源与两语言时间按BR-07校验，部署映射不进入普通API。源码、输入、原始输出和后端ticket在repr中隐藏；缺指标保留None。本阶段23项纯端口/配置测试不代表真实隔离验收。
