# B 线接入实施计划：主线同步后的增量

日期：2026-10-29；实施人 B祝祎帆，成员评审人 A覃锐谦。

基线为 main `ec3fb0bd8449700dfd4a9e69d1910d31d0f268e1`。本计划修订[10月24日计划](2026-10-24-p0-b-foundation-and-isolation.md)中尚未实施的底座步骤；旧文件保留供追溯，冲突处以本计划待审方案为准。当前状态和实测结果见[项目状态](../project-status.md)。依据仍为[架构](../02-architecture.md)、[接口](../03-api-contract.md)、[质量门槛](../07-quality-and-acceptance.md)及[工作流](../../CONTRIBUTING.md)。

## 1. 新基线带来的变化

- A 已提供 P0 前端、56方法契约片段、生成客户端和 P1 教学模块；无需重建这些工程。
- `tools/check_all.ps1` 已存在，串联 web、A 真实数据库、模型离线检查。B 只能在保留现有检查的基础上扩充。
- A 已有 a001—a004 SQL 快照、Alembic 独立链和数据库约束。正式迁移要承接实际 A DDL，不能用空迁移宣称集成完成。
- A 的 Repository/Effects、PreflightPort、AssignmentCoordinationPort、FeedbackSubmissions 已有代码定义。B 应适配现有语义，接口修改先双方审查。
- A 验证 host、SqlRepository、合成预检与测试身份仅供独立测试，不直接改名为生产服务。

## 2. 阶段与提交边界

| 阶段 | 文件范围与输出 | 验证与退出条件 |
| --- | --- | --- |
| S0 同步与交接核对 | 本计划、既有准备文档、项目状态；B 分支快进最新 main | 链接/追踪/归档、工具回归、差异检查；核对实际代码与交接一致。完成后请用户提供本阶段提交说明 |
| S1 最小共享事务底座 | `server/pyproject.toml`、`uv.lock`、`app/shared/{database,uow,clock}.py`、`tests/shared/`、`tools/check_server.ps1`；更新唯一入口/CI | 先失败再实现：事务成功提交、跨步骤失败全部回滚、数据库实际时钟、缺测试库失败、子进程退出码；真实 PostgreSQL 16 测试，加已有 A/web/工具回归 |
| S2 正式迁移与 A 存储接入 | `server/migrations/`、`server/alembic.ini`、`app/shared/{metadata,repository,effects}.py`、对应集成测试 | 正式单 head，空库与带数据升级，A 不可变触发器/约束保留，同事务审计/事件失败回滚；保留 A 独立链作为验证路径，不让同一正式库运行两条链 |
| S3 HTTP 与契约联通 | `app/main.py`、`app/api/`、配置与错误处理、`specs/openapi.yaml`、B 契约片段、CI；与 A 协调生成入口 | 当前实现路由、生成契约语义对照、安全字段/错误/会话/CSRF/Origin测试；真实浏览器连接总应用；未实现路由仍明确不可用 |
| S4 执行适配离线验证 | JudgePort、Judge0 适配、profile允许列表、单元/契约测试 | 创建不确定不重复创建；未知状态/资源证据映射、秘密不泄漏、无物理清理证明不释放槽位；替身通过不算隔离验收 |
| S5 独立 VM 实测 | `infra/judge/`、受控安全样例、真实验证入口和环境报告 | 10月24日计划 V-01—V-06及物理退出/清理实测，冻结实际语言和镜像；不足保持阻塞，不运行于业务宿主 |

每阶段验证并形成明确变更摘要后，请用户提供中文提交说明，再执行精确暂存和提交。提交不代表成员批准、主线合入或业务 Done；推送、合并、部署按工作流另行核验授权。超过3工作日或过大阶段拆成兼容小PR。

## 3. S1 具体输入输出与测试

关联 BR-02、NFR-09/12/16，承接 P0-B1。

- 使用 Python 3.12—3.13、SQLAlchemy 2.0、psycopg 和 PostgreSQL 16，版本范围兼容 A 的锁；B 总工程自己的依赖锁固定实际解析版本，不修改 A 独立锁。
- 顶层 UoW 管理一个 SQLAlchemy Connection 事务，以适配 A 的 Repository/Effects。进入时 begin，正常退出 commit，任何异常 rollback 并释放连接。参与服务不自行 commit，不用独立 Session 给各模块另开事务。
- 时钟在该 Connection 上读取 `date_trunc('milliseconds', clock_timestamp())`，返回带时区 UTC；测试证明同事务内等待后读数前进，而非事务开始时间。
- 测试使用显式 `_test` 库与随机 schema，只清理本用例创建的 schema；缺少环境变量或数据库不可达必须失败，不能用 SQLite 或 skip 替代。
- 测试表只在测试 schema 创建。本阶段不部署业务表，也不将其称为正式迁移完成；正式迁移门槛由 S2 满足后才可宣布底座集成可用。
- `tools/check_server.ps1` 执行锁一致性、Ruff、mypy、共享层真实数据库套件；`check_all.ps1` 保留所有既有检查并追加 B 检查。S1 不启用生产 HTTP 或真实执行器。

先编写下列行为测试并记录失败，再实现：

1. 两次写入在同一事务内，第二步抛异常后两次均不可见；成功时另一连接可见全部写入。
2. 约束异常、调用方异常及 commit 失败都不能留下部分事实或泄漏已占用连接。
3. 两次数据库时刻读取前进且为毫秒精度 UTC；不依赖客户端时钟。
4. 无测试库配置立即失败；schema 名称隔离，不能清理其他 schema 或默认 public。
5. B 子检查失败能经独立 PowerShell 和 `check_runtime.py` 返回非零；保留既有故障传播测试。

计划验证：`uv sync --locked --project server`；`uv run --project server ruff check app/shared tests/shared`；对应 format/mypy；`uv run --project server pytest tests/shared`；最后根目录 `python tools/check_runtime.py`、仓库检查、工具回归和差异检查。上述 B 路径尚未实现，当前不能声称命令已通过。

## 4. A/B 交接逐项落地

| 现有交接 | 接入要求 |
| --- | --- |
| `identity.ports.Repository/Effects` | caller-owned transaction；会员变化/停用账号在同一事务更新作业 revision/epoch、审计和Outbox |
| `problems.ports.PreflightPort` | enqueue/read/evidence均在同一UoW；真实版本快照与摘要完整绑定；测试合成证据不能进入正常启动 |
| `Assignments.admission()` | 取得规定锁后调用，冻结返回的 version_id/profile/mode/accepted_at/assignment_revision；profile必须再经B部署允许列表核验 |
| `AssignmentCoordinationPort` | 接通重评互斥、公平与成绩状态；缺适配继续503，不使用空实现放行 |
| `FeedbackSubmissions` / `Learning.resolve()` | attempt终结时冻结帮助引用；读取返回最小授权字段，不混入源码或执行原始输出 |
| `TeachingIntegrations` / `FixedHelp` | B注入提交/预检服务与结果组件；沿用A未知受理快照及幂等键；轮询带后台信号，服务端调用 actor(activity=False) |
| A metadata / a001—a004 | 提取统一metadata前验证表/约束名称一致；A历史SQL快照不原位修改，正式链明确版本来源；B表进入时补跨线外键 |
| A canonical OpenAPI | Cookie、枚举、profile和错误细节仍是待双方确认提案；总契约合并遇同名冲突报错，不能静默覆盖 |

正式 Repository 的分页/有限历史查询不能靠截断 `rows()` 返回值实现，否则会改变A的业务含义；需要显式查询端口与A服务配套调整。正式锁机制替换A验证适配器全局advisory lock时，必须覆盖成员停用、受理、延期、重评等并发测试。

## 5. 当前确认与回退边界

上次用户确认 A 尚未审阅。S0文档已提交为37e3a40后，用户再次明确要求继续下一阶段，本轮据此推进S1本地实现和验证；这不构成A成员审批。A的独立审查、正式合并审批仍待落实，不把A的开发计划审查当作B的审批。

本机 Git author 为 Dollela / 2098349345@qq.com，用户已于2026-10-29确认其为 B 本人使用的已验证邮箱；标题按 `（B祝祎帆）类型: 中文说明`。不自行更改共享仓库作者配置。

S0 无业务数据变更，撤回本次文档提交即可；S1只新增共享库和专用测试资源，回退对应增量但保留测试证据。S2以后持久化回退需核对schema兼容与备份，不执行破坏性downgrade。
