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
