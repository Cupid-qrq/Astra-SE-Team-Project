# P1-B1预检HTTP与教师页面接入计划

> 使用Superpowers executing-plans逐任务实施，TDD先失败后通过，整批完成后一次独立审查。

**Goal:** 教师可在正式应用受理和查询持久预检，刷新恢复查询；发布继续由服务端核对真实终态证据。
**Architecture:** 复用b006账本、A题目服务与认证事务。公开部署profile只用于冻结允许列表，不伪造Judge0语言ID或开启执行。两条B路由进入总OpenAPI，前端接真实传输。发布证据和草稿删除补完整性边界。
**Tech Stack:** FastAPI/SQLAlchemy/PostgreSQL、React/TanStack Query、现有Playwright。
**Spec:** [FR-07与规则](../01-requirements.md)、[接口与PreflightPort](../03-api-contract.md)、[数据设计](../04-data-design.md)、[v0.4工作流](../../CONTRIBUTING.md)。

实施B祝祎帆；成员评审A覃锐谦待真实确认，另作独立代理审查。用户已授权继续阶段开发、按建议中文标题提交和B分支推送。本阶段按既有批准接口实施，不重新开展技术选型问答。分支从main 2dee45c独立创建，不依赖尚未合并的容器PR#6。

## Global Constraints

- 身份、归属、revision、时间由服务端校验；同一请求事务受理任务/点/队列/审计/Outbox，不执行程序、不联网。
- 不重复独立VM/攻击/高压门槛。没有Worker完成写入器，本阶段真实任务仅QUEUED，不伪装PASSED；测试合成终态仅测试库夹具。
- 公开状态只含UUID、摘要、语言/点键、状态、判定，不含冻结blob、隐藏输入输出、源码或engine_meta。
- 配置允许列表与已安装执行器证明分开；复用ASTRA_PROFILES_FILE，不能靠虚构language_id构造RuntimeProfile。
- 独立B工作区；主目录用户暂存文件不动。回退撤销对应阶段提交；如新增迁移，按显式可逆迁移退回并保留历史快照。
- Browser插件未列出，按Build Web Apps说明使用项目已有Playwright；截图/日志写忽略目录，测试不降超时或跳断言。

## Task 1: 正式预检接口与纯profile绑定

Files: server/app/adapters/judge_profiles.py、app/modules/judging/domain.py、preflight.py、app/main.py、app/api/preflights.py；specs/openapi.yaml及实现登记；server/tests/shared/test_preflight_http.py、test_preflight_plan.py、test_api_contract.py、apps/web/src/lib/api/contract.test.ts、server/tests/judge对应profile回归。

Interfaces: SnapshotCatalog只验证公开profile/BR-07且绑定完整摘要；RuntimeProfile仍要求真实正整数语言映射。POST /problem-versions/{id}/preflight(expected_revision)→202 receipt；GET /preflights/{id}→200安全明细；自动轮询遵守X-Astra-Background。

- [ ] 写失败测试：受理/去重/完整冻结、刷新后GET、过期revision、学生/管理员/跨课教师、归档/停用、事务后段失败整体回滚、缺配置503、公开响应不含私密材料；公共SnapshotCatalog不产生执行语言ID，严格profile与摘要漂移拒绝。
- [ ] Run: `uv run --locked --project server pytest server/tests/shared/test_preflight_http.py server/tests/shared/test_preflight_plan.py`。Expected: 新功能缺失导致失败。
- [ ] 最小实现目录/路由/事务组合，总契约新增两项并更新生成客户端；已有A契约保持A范围。
- [ ] Run相同pytest、profile专项、契约导出与类型检查。Expected: 全通过。提交`（B祝祎帆）feat: 接通持久预检受理与状态接口`。

## Task 2: 发布证据与删除引用完整性

Files: judging/preflight.py、problems/application.py（可选删除保护回调）、main.py；必要时judging/models.py、problem models及b009迁移/迁移与readiness回归。

Interfaces: 发布仍消费PreflightPort.evidence完整匹配版本/内容/profile/点集合；带预检记录草稿删除返回409并保留所有材料。若添加发布反向FK，用(version_id,preflight_id)关联，不能只确认预检UUID存在。

- [ ] 写并运行失败测试：仅正确同版本全AC证据可发布；缺/未完成/失败/旧摘要/其他版本拒绝；审计失败回滚；预检后删除409无部分删除；跨版本/不存在发布引用数据库拒绝。Expected: 缺失边界失败。
- [ ] 最小补齐保护及新迁移，禁止修改历史迁移。Run真实PG相关套件、空库/上版升级。Expected: 全通过。
- [ ] 提交`（B祝祎帆）feat: 约束预检发布证据与草稿引用`。

## Task 3: 教师页面真实传输与刷新恢复

Files: apps/web/src/features/integrations/teaching.ts、lib/api/client.ts、schema.d.ts；VersionMaterials.tsx及对应测试；apps/web/e2e-integration/preflight.spec.ts；适用正式测试harness、docs/project-status.md、server/README.md及阶段记录。

Interfaces: 复用既有预检区域，无重设计。真实POST后显示QUEUED并通过背景GET轮询；只在URL保存任务UUID/revision以供同页刷新恢复，服务端每次鉴权；内容revision变化后旧任务不得解锁发布。提交服务继续保持原状。

- [ ] 先失败单元：真实API方法/背景头、刷新任务指针、revision变化、跨版本响应不被接受、未保存材料不能受理；再实现最小接线。
- [ ] 真浏览器：教师建完整草稿→发起→QUEUED→刷新仍可查；后台轮询不续期；缺配置/权限错误如实展示。桌面和移动至少一次，页面/console/交互/截图证据存忽略目录。正式B host实测，A独立host明确保持未接入口。
- [ ] Run相关Vitest、真实PG和Playwright专项，Expected: 可见任务来自数据库，不是Mock或合成完成；发布保持不可用直到真实完成证据。
- [ ] 更新说明并提交`（B祝祎帆）feat: 接通教师预检查询与刷新恢复`。
- [ ] 一次整批fresh代理审查，重要问题一轮TDD修复；无复审。最终一次`tools/pre_push.ps1`完整入口，通过后推送新B分支并建草稿PR/核对CI，不自动合并。

## Review Focus

1. profile元数据与执行器映射混淆，不能分配假的Judge0 ID。
2. 未授权读先读取blob、错误链或日志泄漏私密内容；响应字段必须显式投影。
3. 并发内容修改/重复受理/revision冲突和事务后段失败不能留下半个任务。
4. URL任务指针可被篡改；跨版本/过期revision/账号切换不能显示错误的可发布结果，最终仍由服务端决定。
5. 发布反向FK与不可变触发器、迁移单head、带历史任务草稿删除的错误语义一致。
