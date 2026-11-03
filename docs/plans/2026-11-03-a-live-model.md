# A 线真实模型与独立交付计划

> 实施使用 project-superpowers:subagent-driven-development / executing-plans；业务修改先失败回归，再实现，最后独立审查。

**目标：**完成用户已授权的 A 线模型接入、独立运行验证与交接资料；B 仍负责评测、提交和成绩，完整联调等 B 基本完成后进行。

**设计依据：**docs/06-roadmap.md 的 P0-A4、P2-A2/A3、P3-A2/A3，以及 docs/07-quality-and-acceptance.md。延续现有 Sources、HintService、run_one 和冻结配置；不新增另一套业务队列或模拟生产提交。

**授权与边界：**用户于2026-11-03提供官方 deepseek-flash、https://api.deepseek.com、Windows 用户变量 DeepSeek_API，并授权20元本轮测试总预算。密钥仅内存读取，不回显、不落库、不入提交；只发送自编公开题目与合成学生程序。项目总体500元规范不代表本轮获准支出，运行及测试均采用更严格的20元累计限制。禁止自动重试收费请求，费用未知保留预占。模型外部测试与 B 联调分开登记。

**架构：**在现有适配器上显式选择非思考模式，新增严格配置/凭据读取和独立 Worker 组装入口；HTTP 和 Worker 共享冻结配置ID，缺少 B 来源继续关闭。用独立真实调用工具冻结输入与首轮结果、持久化费用预占；质量评分仍要求实际两名评审，不将代理评分伪装成人工 A/B 签字。官方模型别名不声称永久不变，记录返回版本及核验日期。

**技术：**Python/FastAPI/SQLAlchemy/PostgreSQL、HTTPX；保留 React/Vite 页面与现有端口。

## 重点边界

- 配置缺失、伪造价格、密钥错误不得启动收费调用或泄漏异常内容。
- 重启、并发执行及未知费用不得绕过20元本轮上限。
- Worker 网络调用不得持有数据库事务；过期任务不重复外发。
- 缺 B Sources 不可由合成提交替代；合成数据只用于独立测试。
- 模型返回完整代码、无效结构或截断内容应降级；规则过滤不能宣称语义安全保证。

## 1. 运行配置及独立 Worker

- [x] server/app/adapters/deepseek.py：非思考模式、版本及价格一致性、严格回执和无敏感异常；对应 tests/shared/test_deepseek_transport.py 先验证失败。
- [x] server/app/modules/learning/model_runtime.py 及 hint_worker.py：显式配置加载、环境变量引用、冻结配置初始化及 Worker 事务工厂；与既有 Sources 可注入组合，默认关闭；新增离线与真实 PG 回归。
- [x] 本轮部署限制项目累计20元；复用 HintLedger 预占，旧默认500元仍用于未显式收紧的既有契约测试。
- [x] 验证：目标 pytest、ruff、mypy；记录RED/GREEN。回退：停止 Worker、撤销配置入口，历史账本保留。

## 2. 真实调用与质量材料

- [x] tools/model_live.py、tools/tests/test_model_live.py：显式 live 开关、输入哈希、独占账本、调用前持久预占、未知费用留存、不自动重试；使用与业务相同适配器。
- [x] specs/model/quality-cases.json：自编30例 CE10/WA8/TLE8/RE4，公开上下文与预期原因分离；冻结后才执行，首轮结果不挑选。
- [x] 官方价格/条款/模型核验、连通及质量首轮，保存忽略目录中的证据与费用摘要；不得以 schema 检查代替人工质量评分。
- [x] 验证预算重启/并发/中断与敏感日志测试、实际小额调用；失败后先查原因。

## 3. A 页面与交接

- [x] 核对 A 页面空态、错误、键盘、窄屏与跨浏览器；发现实际缺陷则先失败回归并修复，不重做视觉风格。
- [x] docs/a-user-guide.md、docs/a-integration-handoff.md：可执行教师/学生流程、真实与模拟边界、B接入表、后续真实参与者验收清单。
- [x] 更新当前项目状态/运行说明/模型配置示例，历史记录保持原样；5名非开发者测试和 B 成员评分未发生时保持待办。

## 4. 完整验证与交付

- [x] 独立代理审查（明确不是B成员审批），修复重要项。
- [x] python tools/check_runtime.py、仓库/工具检查、diff检查；本地已通过并分项提交，最终预推送与远端CI以本分支PR记录为准。
- [x] 不合入队友进行中的 B 分支，不把独立模型结果记作整站联调。A分支按已有用户授权交付，远端合并/CI状态以实际PR为准，平台保护如实遵守。

## 本批结果边界

独立代码与材料完成，详见本批报告。三轮合成模型回归的严格质量目标均未全通过；A/B人工评分、5名参与者、Firefox环境及B端到端联调保持待办，不由上述工程清单追认为完成。
