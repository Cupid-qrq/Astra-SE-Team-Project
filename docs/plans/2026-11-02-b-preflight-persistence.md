# P1-B1a预检持久化与事务查询实施计划

> **For agentic workers:** 使用superpowers:executing-plans在既有B worktree实施；TDD；结束时一次fresh whole-range审查。用户授权连续推进、建议中文标题逐阶段提交及检查后推送，2026-11-02明确选择“先推进预检持久化，评测VM稍后补齐”。

**Goal:** 在正式PostgreSQL单链中落地预检任务、测试点、独立待执行队列，以及A PreflightPort兼容的事务受理/查询；本阶段不接生产HTTP或Worker，不开启正式执行。

**Architecture:** 沿用v0.3、A题目快照/摘要与PreflightPort，B同UoW/策略锁/审计Outbox。冻结私有bytea快照，公开读取只投影标识/状态；全语言全部样例/隐藏点形成独立预检队列。新建任务只为QUEUED，不存在正常启动的合成PASSED通路。

**Tech Stack:** Python3.12、SQLAlchemy2、PostgreSQL16、Alembic、pytest；不增加服务或依赖。

**Spec:** [需求](../01-requirements.md)FR-07/BR-04/05/06/07/12、[接口](../03-api-contract.md)PreflightPort、[数据](../04-data-design.md)preflight三表、[路线](../06-roadmap.md)P1-B1、[工作流](../../CONTRIBUTING.md)。基线main 822687c9cdadf049d342f005fd9cef7f8abe53ff；实施B祝祎帆，成员评审A覃锐谦。

## 设计与阶段边界

用户指定oldali已只读SSH连通：Alibaba Cloud Linux3、KVM、2vCPU、约1.8GiB内存、39GiB磁盘，无容器/隔离工具；低于4vCPU/8GiB/60GiB/4槽目标，存在若干本地监听服务，未改配置/安装/运行探针。用户选择延后VM，I0/S5保留未验收；允许按既有契约先做P1独立持久化，不能据此标FR-07完成。PR#4已合入，API未记录非作者审批，状态如实保留待补。

## Global Constraints

- 一个caller-owned事务；先policy_guard，再身份/课程/版本核验与版本行锁；锁内绝无网络或程序执行。
- 版本/内容摘要/profile摘要/revision/私有快照/点集合创建后不可变；历史终态不可原位改写。
- 来源身份、教师状态、归属、时间由数据库决定；后台只读不续会话。学生、跨课教师、停用账号不能读取隐藏材料或任务状态。
- 允许1—2语言，每语言1—3样例及1—10连续隐藏点；参考程序每语言恰好一个，64KiB与UTF-8规则沿用A。bytea冻结支持合法NUL，不转存JSONB隐藏材料。
- 活跃任务按version/content/profile去重，重复不增加job/审计；内容变化后新任务保留旧快照。预检不进入普通/重评调度比例与学生容量。
- 本阶段job仅READY入队；租约/槽位随后续Worker及execution_slots迁移落地，避免没有实际引用表的假外键。evidence仅在完整PASSED/全点AC时返回，当前服务没有写终态入口；测试合成状态仅在专用数据库夹具，生产无注入入口。
- 新版本b006；历史b001—b005及A SQL不可原位改；统一metadata零差异，所有新FK有索引。版本引用RESTRICT防丢失队列事实，公开预检HTTP接线前另行适配A删除引用冲突。
- 源码/隐藏输入输出及私有快照不得出现在repr、错误链、审计/Outbox或普通读取。数据库故障转换为固定安全错误，退出捕获块后再抛。
- 正式HTTP/前端不接线；保持现有未接执行端行为，完整回归保留。迁移回退禁破坏性downgrade。

## Review Focus

1. 并发重复受理及事务后段失败：最多一套活跃run/cases/job；审计/Outbox失败不留部分事实。
2. 内容/profile变化及私有NUL字节：旧快照不被覆盖，新摘要使用A算法，读取不回显材料。
3. 伪造actor角色/跨课程/账号停用：数据库复核后才查点明细；未知任务不泄漏其他课程。
4. 伪造/残缺PASSED：必须精确覆盖全部语言样例和隐藏点，当前没有生产完成写入或HTTP合成证据入口。
5. 迁移/历史引用：升级保存A数据、单head、metadata一致，修改冻结字段和终态被数据库拒绝；不为后续槽位假造外键。

### Task 1: P1-B1a持久化与事务端口

**Files:** Create server/app/modules/judging/{__init__,domain,models,preflight}.py、server/migrations/{versions/b006.py,sql/006_preflight.sql}、server/tests/shared/{preflight_fixtures,test_preflight_plan,test_preflight_storage}.py；Modify server/app/main.py（就绪head随b006更新）、server/app/shared/{metadata,effects}.py、server/tests/shared/test_storage.py、server/pyproject.toml、tools/check_server.ps1、server/README.md、docs/project-status.md；Create docs/reports/2026-11-02-b-preflight-persistence.md；必要回归修复apps/web/src/features/courses/{CourseForms.tsx,CourseForms.test.tsx}和e2e-integration/course-refresh.spec.ts。

**Interfaces:** FrozenPreflight(version_id,version_revision,content_digest,profile_hash,cases,blob[repr隐藏])由freeze_snapshot(snapshot,catalog)产生；TransactionalPreflight(repo,catalog,effects)实现A PreflightPort.enqueue(repo,actor,version_id)/read(repo,actor,preflight_id)/evidence(repo,preflight_id)，拒绝跨事务Repository。enqueue返回preflight_id/state/content_digest；read/evidence仅安全标识/状态/点判定，终态写入与真实执行留后续Worker。

- [x] 读取既有B199后端基线结果；编写纯失败测试：A摘要一致、两语言全部点、profile漂移、连续点/重复参考程序、UTF-8/字节上限、NUL和敏感repr/错误链。Expected: 缺模块失败，随后最小冻结实现通过。
- [x] 编写真实PG失败测试：b006单head与保留数据升级；同事务三表/审计Outbox；重复去重和双连接竞争；A真实草稿创建/私有快照/权限/停用；任务终态/冻结字段约束、PASSED精确覆盖/失效；故障整体回滚与安全错误。Expected: 新表/端口尚不存在而失败，最小实现后通过。
- [x] 增加正式SQL和metadata、事务端口和B严格类型（仅A保持原宽松策略），检查入口包括新模块；旧HTTP/前端行为保留。Expected: 库与真实PG回归、Ruff/format/mypy及根完整入口均退出0。
- [x] 完整回归发现的建课首屏缓存竞争先做单元/真实PG浏览器RED→GREEN，不改超时/重试；以独立中文fix提交；随后提交本任务持久化文件。
- [x] 更新状态及报告，明确仅独立持久化产物；精确暂存并提交“（B祝祎帆）feat: 建立预检任务持久化与事务查询端口”。再用task-done运行该任务的B完整后端套件，记录提交范围。

## 验证与收尾

uv run --locked --project server pytest -c server/pyproject.toml server/tests/shared server/tests/judge；python tools/check_runtime.py；仓库静态、19工具回归、差异、中文提交检查。一次fresh审本批与规范；Important一次RED→GREEN修复及全入口，无复审。正式pre_push检查后按现有授权推新B功能分支，不创建PR/合并/部署/向A发消息。回退新增库与兼容接线，不删除已生成事实或执行破坏性迁移。
