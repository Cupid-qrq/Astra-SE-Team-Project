# B审查补齐与HTTP接入实施计划

> **For agentic workers:** 使用 superpowers:executing-plans 在当前会话逐项执行，TDD并保存独立审查结论。任务勾选不代表A成员批准或业务Done。

**Goal:** 补齐S2组合并发验证，再完成S3正式HTTP和前后端契约联通，每阶段完整验证后本地提交。

**Architecture:** 沿用v0.3模块化单体、A领域/应用服务、B正式迁移与共享Connection/UoW。生产应用不导入server/a_line或测试夹具，不在启动创建业务数据。所有请求事务先策略锁，再解析身份及业务锁；网络不在锁内。延用A页面和视觉，不重做UI。

**Tech Stack:** Python3.12/FastAPI/SQLAlchemy2/PostgreSQL16、JSON Schema、pnpm11.21.0/React/Playwright。

**Spec:** [需求](../01-requirements.md)、[架构](../02-architecture.md)、[契约](../03-api-contract.md)、[S1/S2计划](2026-10-29-b-integration.md)、[工作流](../../CONTRIBUTING.md)。实施B祝祎帆，成员评审A覃锐谦；用户2026-11-01授权连续实施与按建议标题本地提交，故不重复逐阶段请求确认。用户另行明确授权检查通过后推送B功能分支；A批准、merge、部署分别待办。

## 需求关联与验证归属

| 任务 | 关联规则 | 本任务验证边界 |
| --- | --- | --- |
| R | FR-01/03/04、FR-11受理资格前置；NFR-08/12/16/17 | 组合锁、身份、时刻和回滚；不交付提交账本 |
| S3a | FR-01—06/08—10/19/24；NFR-07/08/12/14/16/17 | 正式HTTP装配与协议；保留各需求尚未验收的部分 |
| S3b | FR-01/03—06/09/10/19；NFR-14/15/16/23 | 正式应用浏览器与契约一致性；仅Chromium三视口，非全部浏览器/用户验收 |

R增补验证配置文件为apps/web/playwright.config.ts、vite.config.ts；S3a补充server/.env.example及联调总时限配置，具体原因见报告。角色、FR原归属和成员审批不因装配转移。
## Global Constraints

- 采用正式单head，不修改已提交历史迁移；测试只用专用_test库随机schema；真实评测/收费模型不运行。
- 用户/角色/时间/归属由服务端决定。401/403/404、409冲突、422字段、400语法、413体积、429个人限制、503暂不可用，统一安全错误体。
- Cookie HttpOnly/Secure/SameSite=Lax；写请求检验Origin与CSRF；后台轮询不续会话。
- 公开列表查询使用SQL限量、稳定游标及授权条件；原A rows内部语义不截断。未接通的预检/成绩/提交等明确不可用，不伪造业务成功。
- 完整根入口python tools/check_runtime.py保留A独立套件；每阶段本地提交。提交不等于Done，最终新鲜独立分支审查与A批准分开。

## Review Focus

1. 锁等待跨截止必须读取锁后数据库时刻；Task1实际双连接验证。
2. 停用后旧actor/会话不可继续写；Task1验证，Task2装配锁后身份解析。
3. 登录失败的Fault(commit=True)只提交失败账本，不被普通回滚吃掉；Task2精确测试。
4. 非法JSON、重复字段、超大正文、异常驱动不回显敏感输入；Task2错误协议测试。
5. 生成客户端、canonical schema、实际路由不能互相冒充独立证明；Task3检查生成差异和未实现方法边界。

### Task 1: R—S2组合并发与审查记录补齐

**Files:** Create server/tests/shared/test_admission_concurrency.py、tests/shared/teaching_fixtures.py；Modify server/README.md、docs/project-status.md；报告放docs/reports。

**Interfaces:** 使用SqlRepository(Connection)、TransactionalEffects(repo,request_id)、Identity.actor/update_user、Courses.member、Assignments.admission，全部基于正式迁移和真实数据库时间。

- [x] 编写双连接线程协调用例：成员停用先提交后等待受理拒绝；受理先完成则先受理后停用；账号停用后重新解析身份拒绝；等待跨due_at拒绝FORMAL；成员/账号变更审计/Outbox失败时会话/成员/revision/epoch回滚。
- [x] 运行 `uv run --project server pytest -c server/pyproject.toml server/tests/shared`。Expected: 新回归可在既有正确行为上直接通过；属于补覆盖，不虚构RED。用临时变异去掉guard/时钟锁后取值时必须失败，生产不引入测试开关。
- [x] 修正README旧总览；记录插件版本和本轮真实使用，保留过去未加载的事实。实现有缺陷时先复现后最小修复。
- [x] `python tools/check_runtime.py`、仓库/工具/差异检查。Expected: 退出0。提交 `（B祝祎帆）test: 补齐正式存储组合并发与审查验证`。

### Task 2: S3a—正式HTTP、安全协议与业务装配

**Files:** Create app/main.py、app/api/{contracts,errors,teaching,lists}.py、app/shared/{config,passwords}.py、server/tests/shared/{test_http,http_fixtures}.py；Modify pyproject/uv.lock/check_server，说明和报告。

**Interfaces:** `Settings(database_url:str, session_secret:bytes, origin:str, readiness_token:str)`；`create_app(settings:Settings|None=None, *, engine:Engine|None=None)`；生产仅加载真实配置，Engine可供测试注入。`Contract(document)` 校验所有请求/响应；初期读取A fragment，Task3改为总契约。应用服务不导入A验证host。

- [x] 先写失败测试：缺配置/非法origin；真实DB登录/建课/成员/跨对象；非法JSON400/重复键400；无会话401/CSRF403；Cookie/no-store/request_id；失败登录计数持久化；后台轮询不续期；失败审计回滚；readiness认证与迁移检查。
- [x] 实现独立请求装配：同一个UoW、事务超时和锁后身份解析，Fault(commit=True)在事务内转结果，其他异常完整回滚；错误不回显输入，返回前schema校验。请求逐块限制512KiB。
- [x] 注册A已实现的身份/课程及模块API；公开列表改为服务端限量查询，游标签名绑定用户/路由/过滤条件；短小的测试/参考列表因业务上限固定可内存分页。
- [x] 生产只提供公开liveness、携带内部token的readiness；不在启动seed账号/题目/合成预检；缺外部端口继续503。
- [x] 完整入口与新HTTP测试通过。Expected: 全套退出0。提交 `（B祝祎帆）feat: 接入正式HTTP与统一安全事务协议`。

### Task 3: S3b—总契约、生成客户端与正式应用浏览器联通

**Files:** Create specs/openapi.yaml、tools/check_api_contract.py、server/tests/shared/web_harness.py、apps/web/playwright.server.config.ts；Modify app/api/contracts.py、apps/web/scripts/generate-api.mjs、tools/check_server.ps1、CI/README/status；复用现有e2e-integration。

**Interfaces:** 总契约含A路由和B健康协议；明确A其余未来方法属于设计，生产只注册已实现方法；检查实际注册方法与契约对应，验证请求/响应以及客户端生成差异。YAML用JSON兼容语法存储可避免新增解析依赖。

- [ ] 先验证生成入口和生产运行文档不一致时检查会失败；切到总契约后重生成，A测试仍使用原片段保持独立。
- [ ] 显式测试harness只使用B正式迁移/UoW/Repository/Effects和正式create_app；测试账号/合成已发布版本仅在harness初始化，不进入生产启动。独立scope下重用A浏览器流程，外部端口不足用例按真实503断言，不伪造执行。
- [ ] 真实浏览器覆盖登录/课程/题目/编辑器/固定帮助、会话失效、三视口；Browser技能当前未列出，按frontend-testing-debugging允许的Playwright路径，记录原因。
- [ ] 完整入口（含正式应用浏览器）、工具/仓库/提交检查。Expected: 退出0；未实现业务不计验收。
- [ ] 提交 `（B祝祎帆）feat: 统一接口契约与正式应用浏览器联通`，然后独立新鲜上下文审查整个本轮范围；Critical/Important按RED-GREEN修正并完整复验，必要形成独立修复阶段提交；A批准仍待办。

## 回退

新增应用/契约按阶段兼容提交回退；不删除现有schema或迁移、不改写已提交历史、不push/merge。独立测试schema由创建它的夹具清理。原目录暂存材料不带入。
