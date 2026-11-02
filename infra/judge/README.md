# 可选独立评测VM诊断

课程基础容器准备与单槽冒烟见[课程容器说明](course/README.md)。以下工具仅用于可选严格VM诊断。

v0.4课程交付采用基础受限容器检查，独立VM、攻击探针和高规格压测均为可选后续诊断。本页保留既有严格VM登记工具的真实使用说明；工具仍按自身协议拒绝不完整证据，其结果不作为课程代码合并门槛，也不能自动启用评测。

选择独立VM诊断时，依据[部署规范](../../docs/08-deployment-and-operations.md)、[隔离矩阵](../../docs/07-quality-and-acceptance.md)和[P0-B2计划](../../docs/plans/2026-10-24-p0-b-foundation-and-isolation.md)。专用Linux VM可以位于足额本地物理机或已有远程资源；与业务环境分开，目标4vCPU/8GiB/60GiB SSD、4槽，无超售。当前WSL数据库环境不算评测VM。同宿主受限容器可满足课程部署形式；不能声称因此完成本页的独立VM诊断。

由成员协调VM资源与管理权限；规范没有指定必须由A提供。评测VM禁止持有业务数据库凭据，只向Worker开放鉴权HTTPS管理面；学生运行及编译禁网。监督控制与普通Judge0鉴权分离。本文不提供课程容器启动配置，也不自动安装或部署执行器。

## 登记

复制[模板](deployment.example.json)到忽略目录`.local/judge/deployment.json`，填实际非零VM/deployment UUID、系统/内核/虚拟化、不可变VM/执行器镜像digest和待验收source_sha。资源填实际值，槽固定4；status改为REGISTERED只表示登记，不表示隔离通过。

profiles每项为`{"snapshot": A公开profile完整快照, "language_ids": {"cpp17": 实际ID, "python3": 实际ID}}`，允许某快照只包含已声明子集，但整个部署覆盖两语言。快照必须符合BR-07；摘要复用A的profile_digest，映射版本固定astra-judge0-ce-v1。不要抄公开演示语言ID或凭版本展示名猜镜像。登记中只允许固定环境变量名ASTRA_JUDGE_TOKEN、ASTRA_SUPERVISOR_TOKEN，值由秘密存储注入，不能写入JSON/Git/命令行。

about_hash、languages_hash、config_hash分别是三个只读JSON响应按UTF-8、键排序、紧凑分隔符、ensure_ascii=False的SHA-256。运维先核对官方变更、安全公告及不可变镜像，再冻结实际版本；本仓库不替VM选择未经核验的Judge0版本。`--probe`在登记结构有效时输出所见摘要，差异返回非零，可供成员核对后登记；不输出响应正文。

从仓库根目录运行：

```powershell
uv run --locked --project server python tools/verify_judge.py --registration .local/judge/deployment.json
uv run --locked --project server python tools/verify_judge.py --registration .local/judge/deployment.json --evidence .local/judge/evidence --probe
```

默认不联网，缺证据返回2；模板本身返回UNVERIFIED/2。显式--probe只GET管理端/about、/languages、/config_info及监督端/v1/capabilities。TLS校验保留、环境代理/重定向/重试关闭，响应大小/读取及截止受限。配置漂移、缺能力、网络故障均返回非零，不创建submission，不编译或执行程序。

监督端声明astra-supervisor-v1、同deployment_id/judge_vm_id/登记fingerprint，以及compile_resource_limits、aggregate_run_memory、directory_quota、compile_network_off、run_network_off、run_entities_1、fenced_cleanup、resolve_unknown_create能力。S4b的创建前持久登记/fence、取消及未知创建收敛协议见[服务说明](../../server/README.md)。这只是候选协议，选择此可选诊断时，真实VM监督实现与物理真实性仍需实测；原生Judge0 DELETE不能替代它。

## 实测与证据

选择执行VM攻击诊断时，先确认独立测试环境及监督能力，再由实施人执行V-01—V-06并独立审查；不得在承载真实业务数据的环境运行攻击探针。具体阈值与用例以质量矩阵为准：CPU/墙钟、集合内存、文件与目录、编译、运行实体、编译/运行禁网及受限对象哨兵。正常、超时、Worker失联、未知创建均需实际停止/目录清理/创建收敛/fence证据，无法证明的槽位保持隔离。

每项保存`V-01.json`至`V-06.json`和非敏感聚合观测文件，JSON结构为：schema=astra-isolation-evidence-v1，test_id、result=PASS、synthetic=false、fingerprint（工具输出）、source_sha、performed_at（UTC ISO时间）、operator、不同的reviewer、languages=[cpp17,python3]、artifacts=[{path:证据目录内相对路径,sha256:文件摘要}]。摘要要绑定原始聚合观测；禁止包含源码、隐藏输入/输出、管理token或数据库凭据。单份文件最多2MiB。

工具校验目录边界、登记/源码指纹、每项身份和文件摘要。即使退出0也只输出RECORDED_REQUIRES_MEMBER_REVIEW和execution_enabled=false，不能自动启用正式评测。执行本项可选诊断时，审查人必须审查实际观测、镜像与配置、单位映射和清理证据；结构测试中的合成夹具不是真实S5证明。profile/镜像/配置/映射或执行实现变化后重新绑定受影响实测；不得原位修改历史报告。
