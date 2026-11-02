# P0-B2课程容器基础冒烟

- 日期：2026-11-02；基线：v0.4 / main 2dee45c。
- 实施：B祝祎帆；成员评审：A覃锐谦；本阶段另作独立代理代码审查，不冒充成员审批。
- 依据：[需求BR-07、NFR-04/06](../01-requirements.md)、[基础容器检查](../07-quality-and-acceptance.md)、[部署规范](../08-deployment-and-operations.md)。
- 用户已授权继续实施、分阶段提交并使用oldali测试。此任务采用既有基础容器设计，不新增业务API或改变JudgePort。旧独立VM、四槽高规格和V系列攻击诊断不作门槛。

## 设计与范围

oldali为2vCPU/约1.8GiB，采用系统签名源Podman（无常驻管理服务）与阿里云官方基础镜像，使用固定digest构建含GCC/Python的测试镜像。相比安装全套Judge0服务，此阶段只建设可复现的基础容器冒烟；已有Judge0适配端口保留，正式Worker接入另开阶段。Docker官方源当前不可达，Podman与官方阿里云镜像源可达，这是实施选择，不是用户指定产品。

仅运行仓库内公开合成夹具，不接收学生文件。可信控制脚本可在宿主运行；程序只在容器执行。编译和运行分别使用非root、只读根、禁网、cap-drop、no-new-privileges及BR-07限制；临时工作卷32MiB，文件1MiB，输出有界，编译20秒/512MiB/30实体，运行256MiB/1实体，CPP CPU2秒/墙钟5秒，Python4秒/10秒。单次单槽；退出后确认容器停止并删除本任务资源，失败不宣称槽位可复用。镜像准备联网，编译/运行禁网。

不开放端口，不启用Podman API，不修改宿主防火墙，不挂载宿主源码、业务数据或控制socket；只操作带本次唯一前缀/标签的容器及卷。公开报告只含配置、版本、结果、时长和清理，不能记录凭据或隐藏题目。运行脚本兼容宿主Python3.6标准库；业务Python版本不变。CPU用RLIMIT_CPU，墙钟用宿主控制超时；此脚本不冒充完整业务判定器或CPU/内存度量实现。输出未知指标保持null。

## Global Constraints

- 复用干净B工作区 feat/b/p0-course-container-smoke；保留D主目录的他人暂存和未跟踪文件。
- 固定镜像ID/digest，禁止自动从未验证镜像运行；无shell拼接学生输入。
- 真实容器冒烟与离线边界测试分开；不把后者记为隔离验收。
- 回退：停止并移除本次自有容器/卷；撤销本阶段commit。保留可复用镜像和安装记录，无需为回退卸载共享系统包。

## Task 1: 有界容器控制及失败测试

Files: 新建 tools/course_container_smoke.py、tools/tests/test_course_container_smoke.py。

Interfaces: 提供 restricted_args(image,name,volume,phase,language)、bounded_process(argv,input_bytes,timeout,max_bytes)、run_smoke(image,source_sha)；命令列表调用Podman，无管理网络；输出JSON schema astra-course-container-smoke-v1。

1. 先写失败测试：镜像须sha256固定ID/digest、限制两阶段不同值、无宿主bind/socket/privileged、超时/输出上限终止子进程、有界结果、清理失败不得PASS、报告不含程序输出或输入。使用公开夹具和伪运行器验证控制边界。
2. Run: `python -m unittest discover -s tools/tests -p test_course_container_smoke.py -v`。Expected: 因实现缺失或边界未实现失败，不能依赖环境缺包制造RED。
3. 实现最小Podman控制脚本，内置两语言合成求和、错误、休眠超时夹具，分阶段传入/tmpfs工作卷；采集inspect限制与结果并逐项核对，退出清理。CLI失败返回非零，敏感/原始输出不进入报告。
4. Run同上，Expected: 所有新增边界测试通过；再执行工具套件。

## Task 2: 镜像、真实单槽冒烟与交付

Files: 新建 infra/judge/course/Containerfile、README.md；更新 infra/judge/README.md、docs/project-status.md，新增 docs/reports/2026-11-02-b-course-container-smoke.md。

Interfaces: 消费Task1 CLI；镜像FROM从阿里云官方仓库固定digest；构建仅安装签名系统源gcc-c++/python3，记录实际版本和最终镜像ID。脚本可通过SSH传输至/opt/astra-course-test，仅操作该测试前缀。

1. 预览后从系统签名源安装Podman，不启用服务；拉取官方镜像、记录digest，再固定FROM构建。Expected: 版本可读、镜像有固定ID、无新增网络监听。
2. 实际执行Task1两语言正常/错误/超时冒烟，记录时间与清理，Expected: 全部符合预期且本次容器/卷残留为0。故障如实记录，不能放宽基础限制来凑成功。
3. 文档说明复现、实际环境和限制；项目状态标Review或In Progress，不提前Done。Expected: 不再把旧VM规格当当前阻塞，正式业务执行接入待完成。
4. Run: `python tools/check_repository.py`、`python -m unittest discover -s tools/tests -v`、`git diff --check`；Expected: 全通过。
5. 整分支独立审查，重要问题按失败测试修复。中文阶段commit：`（B祝祎帆）feat: 建立课程单槽容器冒烟与清理验证`。
6. 已提交且工作区干净后运行`pwsh -File tools/pre_push.ps1`，含真实PostgreSQL和既有完整工程检查；通过后按既有授权推送B功能分支，核对远端SHA/CI。Expected: 预检通过，远端HEAD一致；不自动宣称已合入main。

## Review Focus

- 输出/超时使Podman客户端退出时，容器必须单独停止并确认，不能只杀客户端。
- 工作卷大小和权限必须真实生效；只读根的其他可写挂载不得绕开目录限制。
- pids=1时不能为脚本额外套一个shell；C++可从编译卷直接执行，Python解释器直接PID1。
- 失败清理、inspect漂移、基础工具不可用均应失败，不能标成功。
- 真实镜像/运行记录与离线假运行器区分，公开报告不得含原始源码/输入输出。
