# P0-B1 / P0-B2：工程底座与隔离执行实施计划

- 实施人：B祝祎帆；成员评审人：A覃锐谦。
- 需求依据：[开发总纲](../00-development-plan.md)、[架构设计](../02-architecture.md)、[接口契约](../03-api-contract.md)、[质量与验收](../07-quality-and-acceptance.md)、[开发工作流](../../CONTRIBUTING.md)。
- 关联规则：BR-02/05/06/07/11/12；NFR-04/06/09/12/16/17；V-01—V-08。
- 当前任务状态与阻塞只在[项目状态](../project-status.md)维护；本文件定义待评审的实施范围，不作为已完成证明。

## 1. 开工门槛与交接

1. 核对 P0-A1：双方提交身份、插件、设备、可用时间与任务分工。未知项由所属成员确认，不替 A 填写。
2. A 审查本文件中的文件范围、公共接口、失败用例和执行边界后，开始对应实现；审查记录引用本计划的 Git blob 或明确版本。
3. 公共协议、迁移基线、配置命名、检查入口由 B 提供，A 模块的业务契约和迁移由 A 提供；不在本任务代建身份、课程或作业业务。
4. 先完成 B1.1 的可运行底座，再与 A 的 P0-A2/A3 对接；B2 的环境准备可独立推进，真实样例只在经确认的专用评测 VM 执行。
5. A 尚未提供生成客户端时，客户端一致性检查登记为未完成；不使用空文件或跳过脚本冒充通过。

## 2. 分批范围

| 批次 | 输出 | 完成边界 |
| --- | --- | --- |
| B1.1 | Python 工程、配置、错误/请求协议、事务/时钟、健康接口、迁移基线、真实 PostgreSQL 测试和检查入口 | 可从干净检出重建并验证；尚不代表全部 P0-B1 完成 |
| B1.2 | 公共及 B 模块 OpenAPI，与 A 的 schema、客户端和 Mock 合并 | 全路由契约、安全投影、错误和生成差异通过；不实现 P1 业务 |
| B2.1 | JudgePort 类型、适配器、配置/profile 校验、状态映射和故障契约测试 | 替身仅证明协议与错误处理；不能证明执行隔离 |
| B2.2 | 专用 VM 的版本冻结、V-01—V-06 实测、退出与清理证据 | 所有必需限制实际生效才冻结 profile；未通过不得接收正式学生代码 |

每一批独立提交、验证和评审；不把五个人日任务塞进一个无中间检查的大改动。

## 3. B1.1 文件与公共接口

| 文件范围 | 职责/输入输出 |
| --- | --- |
| `server/pyproject.toml`、`server/uv.lock`、`server/.python-version` | 锁定 Python 3.12 与实际解析依赖；FastAPI/Pydantic、SQLAlchemy 2、psycopg、Alembic、pytest、Ruff、mypy、HTTPX |
| `server/app/main.py`、`server/app/api/` | 应用装配与 `/api/v1`；公开 liveness、内部 readiness；统一 HTTP/校验/未处理错误 |
| `server/app/shared/config.py` | 显式环境配置、非安全默认值拒绝、秘密不进入 repr/错误/日志；无数据库配置时启动失败 |
| `server/app/shared/errors.py`、`server/app/shared/clock.py` | 统一错误投影；时钟读取数据库 `clock_timestamp()`，使用带时区 UTC 毫秒，不用事务开始时刻代替当前时刻 |
| `server/app/shared/database.py`、`server/app/shared/uow.py` | 同步 SQLAlchemy Session/顶层事务；参与模块共用一个事务，异常全部回滚，不在内部服务自行提交 |
| `server/alembic.ini`、`server/migrations/` | 唯一迁移链与统一 metadata；初始只建立迁移基线，不伪造 A 的业务表；业务外键随所属模块进入 |
| `server/tests/unit/`、`server/tests/integration/` | 失败场景、HTTP 协议和真实 PostgreSQL 事务/时钟/迁移；测试夹具表仅在隔离测试命名空间创建 |
| `.env.example`、`server/Dockerfile`、`infra/compose/compose.yaml`、`infra/proxy/` | 业务区启动、环境模板、同源反代及 readiness 内网限制；只开放开发所需本机端口，无评测容器 |
| `tools/check_all.ps1`、`.github/workflows/repository.yml` | 统一执行锁文件同步、格式、类型、单元、真实数据库集成、迁移与已引入的契约检查；独立 PowerShell 失败码逐层返回 |
| `server/README.md`、`infra/README.md`、`docs/project-status.md` | 真实启动/检查命令、A 接入说明和未完成范围 |

配置名使用 `ASTRA_` 前缀；数据库、会话/CSRF 密钥引用、允许源、运行模式等必填项和启停规则在实现前由双方确认。模型与执行器默认关闭；不能因缺少凭据退回公开执行服务。

公共错误沿用现有 `code/message/request_id/retryable/retry_after_seconds/field_errors`；不添加并行错误体系。请求 ID 仅接受约定格式，否则重新生成；敏感响应 `no-store`，异常不输出 SQL、URL 凭据、隐藏内容或栈到普通响应。

## 4. B1.1 先失败用例

| 用例 | 首次失败断言 | 最小实现后的结果 |
| --- | --- | --- |
| 配置缺失/错误 | 应用接受缺失数据库配置、非 PostgreSQL URL 或非法安全参数 | 拒绝启动；错误不回显秘密 |
| 错误协议 | 404/422/内部异常不是共同结构，或泄漏原始输入 | 同一 schema；只返回批准的字段和安全错误 |
| 请求关联 | 非法外部 ID 被照搬，或响应没有关联 ID | 重写非法值；响应头与错误体关联一致 |
| 事务回滚 | 第二步异常后第一步写入仍存在 | 全部回滚；成功事务提交一次 |
| 数据库时钟 | 同一事务内等待后时刻仍固定在事务开始值 | 第二次读取实际前进；保存/序列化 UTC 毫秒 |
| 真实数据库必要性 | 数据库不可用时集成套件仍绿色 | 明确失败；不替换为 SQLite、不 skip |
| 空库迁移 | 干净测试库无法到唯一 head，或 metadata 漂移 | 可升级、重复升级无副作用；所有 head 和结构核对一致 |
| 检查传递 | 子检查失败但总入口/`check_runtime.py` 返回 0 | 单元注入失败可观察到非零退出；CI 实际调用同一入口 |
| readiness | 连接失败或迁移版本不符时仍就绪 | 内部返回 503；公开 liveness 不暴露连接详情 |

真实数据库测试只操作显式创建的专用测试数据库/命名空间；无测试连接时失败，不对用户现有数据库执行清空操作。

## 5. B1.2 契约交付

- B 负责公共 schema、预检、提交、成绩/重评、管理、导出和通知 schema；A 负责身份、课程、题目、作业和学习 schema。
- 最终共同形成 `specs/openapi.yaml`（3.1）；每条路由具备参数、角色、安全响应、成功/失败码和样例。
- API、Mock、生成客户端只消费这套契约；A 维护客户端生成配置，B 提供校验入口。
- 未实现的 P1/P2 路由不返回伪造成功，也不被记为业务验收通过。
- 必须先确认的内部边界：身份/课程授权查询、题目执行快照读取、`PreflightPort` 输入/结果、作业受理上下文、跨模块写端口共用事务。
- 预检表位于数据文档 A 分组而执行属 B；模型/迁移文件的具体认领由双方确认后再落库。

## 6. B2.1 适配与安全边界

拟增加 `server/app/shared/judge.py`、`server/app/adapters/judge0.py`、`server/tests/unit/test_judge0.py`、`tests/contract/` 和 `infra/judge/`。具体方法沿用契约中的 `create_case/poll_case/cancel_and_cleanup`，不在业务主机使用 subprocess 编译或运行学生程序。

1. profile 输入包含冻结的语言键/实际版本、编译器/解释器和镜像摘要、编译/运行资源、单位和映射版本。language_id 从实际部署核对，不硬编码公共演示服务的数值。
2. `create_case` 的网络超时或响应不确定转换为 `CREATE_UNKNOWN`；不自动再次创建。HTTP 客户端不启用 POST 自动重试。
3. 原始状态、阶段、退出码和资源证据映射为产品判定；未知/基础设施故障为 SE，不能猜作学生 RE/TLE。未知指标为 null。
4. token、输入/答案、隐藏 stdout/stderr 与认证信息仅在授权内部使用，不进入 API 投影、普通日志或模型上下文。
5. `cancel_and_cleanup` 需要可验证的物理退出和目录清理证明；没有证明保持隔离，不释放槽位。
6. 官方 Judge0 CE 文档的删除接口对排队/运行任务返回 400，不能作为取消运行任务的实现。VM 侧监督能力必须另行验证和审查；不得用 HTTP 删除成功推断进程已停止。
7. profile 缺任一强制能力或证据未完成时，不启用正式执行；不自研沙箱，也不借开网、放宽进程数或删掉清理断言获得通过。

先失败测试覆盖：创建超时、不合法/缺失 token、未识别状态、缺指标、非 UTF-8 输出、HTTP/轮询故障、秘密泄漏、取消无清理证据；HTTP 替身断言请求地址、鉴权头、资源字段和没有自动重试。

## 7. B2.2 真实验证矩阵

| 验收 | 输入/观测 | 通过条件 |
| --- | --- | --- |
| V-01 | 两语言正常程序、忙循环与受控休眠，记录 CPU/墙钟 | C++ 2s/5s，Python 4s/10s；宽限单列并审查 |
| V-02 | 实际触碰内存，读取进程集合度量 | 运行集合 256 MiB 限制生效；不能只检查地址空间参数 |
| V-03 | 分别触发单输出文件和多文件目录边界 | 1 MiB 文件/32 MiB 目录分别有效，正常输出成功 |
| V-04 | 两语言参考程序/标准库编译与编译期限制 | 编译 20s/512 MiB；候选进程线程上限 30 实测；运行参数不冒充编译限制 |
| V-05 | 正常主实体、受控新线程/子进程 | 正常执行通过，运行实体总数 1 且新增被阻止 |
| V-06 | 编译/运行网络探针、宿主/其他任务/数据库/管理入口哨兵 | 编译与运行禁网；受限对象不可读；结束后目录实际清理 |
| 清理证据 | 正常结束、超时、Worker 失联及未知创建 | 实际退出和清理后才复用；无法确认时隔离；不在业务机运行这些样例 |

自编验证程序放在 `tests/security/fixtures/`，远端编排入口拟放在 `tools/verify_judge.py`。先核验目标为人工登记的独立评测 VM、镜像和必需 profile，再允许执行；不接受任意公共 Judge0 地址作为默认目标。

报告记录环境指纹、配置/镜像/样例摘要、实际命令、开始结束时间、原始产物路径与结论。原始产物放受控存储或忽略目录，正文不得含凭据或真实学生信息。未执行项保持未执行；替身记录与真实 VM 记录明确区分。

## 8. 验证入口与退出条件

实施后从仓库根运行：

```powershell
python tools/check_repository.py
python -m unittest discover -s tools/tests -v
python tools/check_runtime.py
git diff --check -- . ':(exclude)archive/submissions/**'
```

`check_all.ps1` 内部从 `server` 执行 `uv sync --locked`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy app`、`uv run pytest tests/unit`、`uv run pytest tests/integration` 和空库迁移检查。数据库必须真实可用。A 的前端/生成客户端进入后，同一入口增加对应真实检查，不留恒成功占位步骤。

真实隔离验证另由批准的专用 VM 执行入口运行，不进入普通 PR CI。CI 只使用 PostgreSQL 测试服务和执行器替身，不持有评测区/生产/模型凭据。

P0-B1 的退出条件为工程与契约真实验证通过并由 A 审查；P0-B2 退出条件为全部必需隔离能力与清理证据实测通过。I0 还依赖 A 的前端联通与双方插件核验。本计划不预先宣布任何一项完成。

## 9. 回退和集成

- 使用独立 `feat/b/p0-foundation-isolation` 工作区，原目录未提交材料不带入。
- 每批提交前检查精确文件范围、完整验证和另一成员反馈；不自动推 main、合并或部署。
- 尚无业务数据时可撤回对应工程提交并删除本任务创建的测试环境；持久业务数据出现后按兼容迁移和备份恢复规范处理，不能盲目 downgrade。
- 提交身份先核对 B 的真实 Git author/邮箱；推送与合并另按 CONTRIBUTING 核验双方依赖和当前 SHA。

## 10. 实现核对资料

- [FastAPI 多文件应用](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [SQLAlchemy Session 事务](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Judge0 CE API：配置、状态和删除限制](https://ce.judge0.com/)

上述资料用于实现核对，不替代本项目的真实数据库、隔离及清理测试。
