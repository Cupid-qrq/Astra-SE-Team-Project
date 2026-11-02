# B执行适配与独立VM验证准备实施计划

> **For agentic workers:** 使用superpowers:executing-plans在现有B worktree逐项实施，TDD；批次完成后一次fresh whole-range审查。用户已授权连续阶段实施、建议中文标题提交及检查后推送。

**Goal:** 完成S4候选执行端口/允许列表、Judge0 HTTP适配和S5独立VM登记/只读预检准备；未登记VM时不执行程序、不宣布S5隔离完成。

**Architecture:** 沿用v0.3独立Linux评测VM、Judge0兼容管理入口及VM监督清理。业务事务与网络分离；本批不接业务Worker/提交账本，不在业务宿主编译或执行代码。A现有profile snapshot及摘要保留，部署语言ID由允许列表绑定，普通API不接收执行器token。

**Tech Stack:** Python3.12、dataclass/Protocol、HTTPX、pytest；复用现有完整入口与真实PostgreSQL套件。

**Spec:** [增量计划S4/S5](2026-10-29-b-integration.md)、[原隔离矩阵](2026-10-24-p0-b-foundation-and-isolation.md)、[架构](../02-architecture.md)、[内部端口](../03-api-contract.md)、[质量](../07-quality-and-acceptance.md)、[部署](../08-deployment-and-operations.md)。实施B祝祎帆，成员评审A覃锐谦。用户2026-11-02转达“A已确认当前交接”；不代填新提交的GitHub审批、A未推送工作或VM实测证据。

## 设计选择

沿用已批准的Judge0+独立VM方案。公开执行服务、业务机subprocess及同VM容器方案与现有规范冲突，不采用。原生Judge0 DELETE不提供运行中取消；监督清理协议为本批候选内部接口，必须由登记VM实现并在S5验证。适配库先保持未接生产Worker；替身全部通过仍不能开启正式执行。

## Global Constraints

- FR-07/13/16/24，BR-04/05/06/07/11/12，NFR-04/06/09/16/17；本批只交付相应基础端口，不标业务Done。
- C++ CPU2000ms/wall5000ms，Python4000/10000；运行256MiB，编译20000ms/512MiB/30实体；单输出1MiB、目录32MiB、运行实体1、编译与运行均禁网。
- 创建一次调用最多一次POST；任何可能已创建而无可靠ticket的结果记CREATE_UNKNOWN，不自动重试。跨调用/崩溃的持久化幂等由后续Worker账本承担，本批不能以进程内状态冒充。
- 正常退出后才比较；适配器不根据Judge0默认AC/WA发放产品AC，不发送expected_output。缺少指标为null；未知状态/平台故障SE，不解析stderr猜学生原因。
- Cleanup只接受同deployment/lease/request/profile的结构化停止、目录清理、创建收敛和lease fence证据；原生DELETE/布尔成功不释放槽位。真实物理正确性仍需S5。
- token/认证头/源码/输入/原始输出repr隐藏；异常、响应、网络日志不泄漏。HTTPS固定登记目标、无重定向/代理继承/公开服务fallback；TLS验证保留。
- 每阶段完整入口及对应检查后本地提交；既有web/A/模型检查保留。push需最新远端、完整pre_push；不merge/部署/向A发消息。

## Review Focus

1. 超时、5xx、错误token/坏JSON时创建可能已发生，不能二次POST；覆盖任务2。
2. profile的bool/int混淆、未知语言、重复ID、摘要/资源篡改必须拒绝；覆盖任务1。
3. 原始二进制输出与日志、异常链、repr不得泄漏隐藏材料；覆盖任务1/2。
4. cleanup证据跨lease/deployment、缺fence/未知创建未收敛不得复用；覆盖任务2。
5. VM预检没有真实V-01—V-06证据时必须明确未验证；文件篡改或任意目标不能通过；覆盖任务3。

### Task 1: S4a执行契约与部署profile允许列表

**Files:** Create server/app/shared/judge.py、server/app/adapters/__init__.py、server/app/adapters/judge_profiles.py、server/tests/judge/{conftest,test_contracts}.py；Modify server/pyproject.toml、tools/check_server.ps1、server/README.md、docs/project-status.md。

**Interfaces:** CaseLease(attempt_id,generation,lease_epoch,testcase_order)；CaseRequest(lease,profile_id,profile_hash,language_key,code,stdin)；ExecutionIdentity/Ticket/CreateOutcome/CaseObservation/CleanupOutcome；JudgePort.create_case/poll_case/cancel_and_cleanup。ProfileCatalog.bind(snapshot)按A profile_digest比较，公开snapshot不含language_id，部署记录提供ID映射。

- [x] 先失败测试：lease各维度/摘要绑定、敏感repr、非法/重复profile、资源常量、未知语言/摘要、部署语言ID不是演示硬编码；读取缺指标保留None。
- [x] 最小纯类型与允许列表；与A摘要算法一致，输入防bool冒充整数、公开snapshot深冻结。Expected: 测试通过、严格类型/格式通过。
- [x] 新套件接唯一入口，完整根入口退出0；报告边界和用户转达确认，提交“（B祝祎帆）feat: 建立执行契约与运行环境允许列表”。

### Task 2: S4b Judge0适配与清理证据

**Files:** Create server/app/adapters/judge0.py、server/app/adapters/judge_mapping.py、server/tests/judge/{test_judge0,test_mapping}.py；Modify server依赖锁/check_server/说明/状态。

**Interfaces:** Judge0Target(HTTPS管理/监督地址、deployment_id、凭据repr隐藏)；Judge0Adapter(target,catalog,transport=None)实现JudgePort，context manager关闭自有HTTPX client。每点生成固定execution key与request/profile digest；监督接口按此关联未知创建及lease fence。

- [ ] 先失败测试：MockTransport断言URL/auth、base64原字节、资源单位/参数、无expected_output、只一次POST；超时/5xx/坏JSON/token不确定；拒绝redirect；固定目标及TLS；敏感日志/repr/异常无材料。
- [ ] 实现有界6MiB响应与各流1MiB、严格base64、状态/退出码/明确资源证据映射；原生3/4正常退出只表示待本方比较，未知/基础设施SE。Python按实际阶段证据，缺指标None。
- [ ] cleanup POST到独立监督协议，校验完整身份/摘要/UUID证明/fence及创建收敛；失败隔离，不用Judge0 DELETE假取消。跨重启持久状态留后续Worker。
- [ ] 完整根入口退出0并报告仅替身验证，提交“（B祝祎帆）feat: 接入Judge0执行适配与监督清理协议”。

### Task 3: S5-prep独立VM登记与只读验证入口

**Files:** Create infra/judge/{README.md,deployment.example.json}、server/app/adapters/judge_inventory.py、tools/verify_judge.py、server/tests/judge/test_inventory.py；Modify check_server、服务说明/状态/报告。

**Interfaces:** 显式登记VM与业务环境不同、4槽资源目标及profile/镜像/语言/映射指纹；verify_judge默认只校验本地登记和证据，--probe才对登记管理端读取about/languages/config及监督能力，不创建submission、不执行任何代码。

- [ ] 先失败测试：占位登记、同VM、公共/任意目标、缺必需能力/实测证据、证据摘要不符、probe网络失败、安全错误均非通过；完整合成夹具只用于结构测试。
- [ ] 最小登记加载、证据检查及有界只读probe；模板默认UNVERIFIED且不能启用。原生参数不能证明编译期/目录/网络/物理清理能力，不自研沙箱或提供弱化默认值。
- [ ] 文档提供专用VM资源与凭据分离、V-01—V-06执行前置/产物清单和后续验证操作，不把当前WSL数据库环境当独立评测VM。
- [ ] 完整入口与工具检查退出0；缺VM时实际实测保持未执行；提交“（B祝祎帆）feat: 增加独立评测环境登记与验证准备”。

## 全局收尾与回退

一名fresh reviewer审本批完整差异；重要项一次RED-GREEN修复及完整回归，Minor登记。当前旧7c95201之后的候选等待A对新实现审查，不代填批准。仅推功能分支，保留工作树；新增纯库/验证入口可兼容回退，不改历史迁移，不删除既有数据/环境。VM尚未登记时S5实测不执行，后续Worker/账本及真实评测开启另行实施。

参考： [Judge0官方API](https://ce.judge0.com/)。2026-11-02核对其鉴权头、资源字段、状态及DELETE排队/运行限制；仅读文档，未向公开服务提交代码。
