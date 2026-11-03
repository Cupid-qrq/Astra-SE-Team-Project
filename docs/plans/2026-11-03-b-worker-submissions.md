# B课程业务闭环连续实施计划

实施B祝祎帆，成员评审A覃锐谦；用户授权连续推进至完成、简化流程、阶段提交与B分支推送。采用v0.4及既有[架构](../02-architecture.md)、[业务规则](../01-requirements.md)、[数据设计](../04-data-design.md)。复用工作区与Superpowers executing-plans/TDD/完成前验证。每批一次独立审查；专项验证先行，最终完整入口，避免重复报告和可选诊断。未实现项不记完成。

基线：预检PR7 b3665fc和容器PR6 97a2a77已在本分支集成424609d，两个原PR仍待合并。A最新模型分支独立保留，后续集成核对，不覆盖其未提交内容。

## Global Constraints

业务进程不直接执行学生程序；数据库事务内无执行器/SSH/网络调用。oldali已验证单槽Podman，固定镜像sha256:e6de72491d3f6b0ecf4bdd998135ed206a7e9b44cc831e1b32d6bd6e74087016。使用成熟OCI运行时，不自研沙箱，不重新要求独立VM、攻击诊断或高规格资源。源码/隐藏数据只通过受控传输及私有工作卷；普通日志/报告不含正文。时间取数据库，迟到写回受generation/lease fencing保护；无法确认清理则隔离槽位。模型配置由A维护。

## Task 1: 真实容器执行接口

Files: tools/course_executor.py、tools/tests/test_course_executor.py；复用tools/course_container_smoke.py的资源策略；server/app/adapters/course_executor.py与tests/judge/test_course_executor.py；infra/judge/course/README.md。
Interfaces: 受控JSON经stdin输入，固定命令SSH到指定别名执行工具；固定镜像/语言/身份/原字节base64；不使用源码命令行、临时普通日志或shell拼接。单执行器文件锁、身份持久登记、取消fence、开始前拒绝旧资源，响应限长。输出受控原字节仅回业务Worker用于比较，日志只常量故障码；CPU/内存未知为null。
- [ ] RED：非法身份/镜像/大小/语言拒绝；固定容器权限与输出限额、正常退出才比较、CE/TLE/RE/SE按实际阶段、重复身份/取消后迟到创建拒绝、清理失败隔离、敏感异常链不外泄。
- [ ] 实现并验证正常/错误/超时、两语言输出、清理与重复请求，合成公开夹具在oldali执行；无业务凭据挂载入容器。
- [ ] Run `python -m unittest discover -s tools/tests -p test_course_executor.py -v`及对应pytest/oldali真实调用。Expected通过，报告明确实际阶段和清理。
- [ ] 中文阶段提交：建立课程受限执行接口。

## Task 2: 预检Worker与恢复

Files: judging/worker.py、worker_store.py、models.py；新b010及静态SQL、readiness/迁移测试；tests/shared/test_preflight_worker.py。
Interfaces: 数据库execution_slots单槽、preflight_jobs租约epoch/截止/创建身份/状态；领取提交后执行，5秒续租/15秒恢复、轮360秒；每点身份在创建前持久化，事务外取消并确认清理才释放。未知创建禁止重复；失联恢复只通过当前fence写回，未确定清理隔离。冻结快照内两语言全部样例/隐藏点，结果通过现有判定规则；失败点及后续状态一致，全部AC才PASSED。
- [ ] RED：并发领取仅一次、事务外执行、全点完成、故障清理、迟到回写、超时、旧epoch/身份拒绝、崩溃后持久恢复、未确认退出不得释放。
- [ ] 实现迁移及CLI单轮/常驻Worker，受控关闭，测试配置与实际部署配置分开。
- [ ] Run真实PG与oldali端到端公开预检；Expected QUEUED→RUNNING→PASSED/FAILED，发布匹配证据；恢复真实验证。
- [ ] 中文阶段提交：接通预检Worker执行与清理恢复。

## 后续连续批次

Task3学生提交受理/幂等/正式性、队列结果与历史页面；Task4成绩快照/发布/基础管理；Task5全量重评/公平/归档与维护；Task6导出/通知/部署恢复和交付。具体文件级接口与失败用例在各批开始前追加本计划，不为未开工内容铺满函数方案。每阶段完成提交，批次审查及完整入口通过后推送草稿PR。最终三角色闭环、独立恢复与共同验收按实际证据记录，需真实参与者的验收不由代理冒充。

## Review Focus

- SSH未知结果与控制器中断时不能重复创建/复用槽位；取消fence须持久。
- 编译、运行、平台失败的判定证据必须来自实际阶段，不能把客户端退出当程序退出。
- 任务领取与所有进度/完成/恢复写回必须检查同一租约及运行身份；网络在事务外。
- 预检私密快照、学生源码只进入已授权执行上下文，不进日志、报告或模型。
- 本分支集成依赖、迁移单head及A后续模型接口需最终核对，不虚构审批或绕过保护。

## Task 3: 学生提交与结果闭环（2026-11-03追加）

授权：用户要求继续完成全部v0.4工作、简化流程；实施B，成员评审A，代理批次独立审查单列。前两阶段已完成并推送PR9，fea64bf的完整本地/CI通过，主线d50b9e9；本阶段复用检出，新分支feat/b/p1-submission-results。

### 3a 持久受理与不可变来源
Files: server/app/modules/submissions/{models,application}.py、shared/metadata.py、新SQL011/b011、tests/shared/test_submissions.py及迁移head断言。
Interface: Submissions.accept(actor, body, key, intent, request_id)返回receipt和replayed，调用者拥有UoW；先policy_guard、身份/已有幂等记录当前授权，再新作业admission取DB时刻。参数不接受user/mode/时间。一个事务持久submission/basis/cycle/attempt/job、容量/间隔、审计Outbox；原始源码/资格/回执不可修改。
- [ ] RED：10路同键一次；异内容409；跨截止重放；停用/越权；3个人/100全局/5秒；意图不降级；副作用失败全部回滚；跨提交结果指针约束；原始内容不可变。
- [ ] b011保存提交、原始及未来重评basis、周期/轮次/队列/容量；延迟复合外键保证归属；本阶段不冒称评测终态已运行。
- [ ] `uv run --locked --project server pytest server/tests/shared/test_submissions.py`及迁移测试，预期真实PG通过。提交中文feat。迁移有业务数据时禁止破坏性downgrade，停止新入口后使用前向修复。

### 3b Worker与安全结果API
Files: submissions/{worker_store,worker,api,sources}.py，judging共享slot调度、main/worker_cli、OpenAPI/生成客户端，shared/HTTP测试。
Interface: 共用单物理槽，先正常学生任务再预检；已持久identity再SSH，事务外执行/取消，epoch fencing。六判定/首错停，最多一次基础设施重试，15分钟cycle/360秒round，释放容量一次；冻结Learning.resolve引用，适配A反馈/提示/学习结果接口。查询与列表当前授权，无隐藏数据/token/stdout。
- [ ] RED：并发claim、超时/失联/迟到、一次重试/周期不重置、回滚/清理失败隔离、权限/秘密字段检查；真实公开夹具经oldali闭环。
- [ ] 修正接口契约并生成客户端；对应pytest通过后中文阶段提交。

### 3c 学生页面与历史
Files: apps/web/src/features/submissions/*、integrations/teaching.ts、runtime/路由接线及e2e-integration/submissions.spec.ts。
- [ ] 复用公共组件，编辑器真实受理/轮询、结果抽屉/详情/历史/轮次；保留A原幂等快照恢复及代码保护，接固定帮助与学习页。
- [ ] 单元失败用例、正式PG三视口浏览器、业务恢复检查通过后阶段提交。

本批一次独立审查，修复重要项后完整入口及远端CI；后续Task4—6沿用上述既有范围，在开工前补齐具体文件，持续执行不再次索取开始许可。

## Task 4: 成绩快照、发布与同版导出

用户16:27授权减少重复测试、19:27前争取验收。Files: 新modules/grades/{models,application,api}.py、b013/SQL013、main、契约/客户端、GradePages及作业入口。复用AssignmentCoordinationPort接线，阶段专项仅保留计分/发布阻断/授权与一个浏览器主流程，最后整批完整检查。
- [ ] 当前有效正式结果每题任一AC得该题全分，未终结/SE阻止发布；只计当前课程成员，截止和公平已决、revision正确才能冻结grade_versions/students/items，同事务审计通知。
- [ ] 固定快照只读，学生仅本人，教师分页；grade_epoch变化显示暂定，历史快照保持；CSV由同一快照生成并转义公式。
- [ ] 真实PG专项验证计分、未完成/SE/截止/公平拒绝、越权和历史一致；完成中文阶段提交。回退使用停入口/前向修复，已有快照不得破坏性downgrade。
