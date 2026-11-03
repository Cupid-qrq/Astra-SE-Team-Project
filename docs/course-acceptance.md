# 课程验收与运行

当前按v0.4提供课程规模的单槽执行，演示前端为生产构建。独立VM、高规格负载和攻击探针为可选诊断。

## 本机演示

```powershell
pwsh -File tools/start_demo.ps1
pwsh -File tools/stop_demo.ps1
```

启动读取工作区忽略目录`.local/course-demo/application.json`。本机地址为`https://localhost:4176`，API监听`127.0.0.1:8021`，评测通过已核验SSH别名oldali的受限Podman运行。证书为七天本地演示证书，首次浏览器访问需确认本机证书。进程清单和日志在同一私有目录，停止脚本仅停止匹配PID与启动时间的演示进程。

演示账号为`teacher_demo`、`student_demo`、`admin_demo`，本机公开演示密码为`AstraDemo2026!`。这组凭据仅用于独立演示库，外部部署应通过本地环境设置新密码。数据库和会话密钥由本机随机生成，未提交仓库。账号初始化脚本只接受空的`*_demo`数据库，已有账号时拒绝覆盖。

## 建议验收顺序

1. 学生进入“开放作业”，使用Python提交`print(sum(map(int,input().split())))`到“两数之和”，查看正式性、实际结果、详情、源码和历史。C++17亦可提交单文件程序。
2. 教师进入“成绩与重评验收”，查看已发布100分成绩并下载CSV，同一成绩版本保持一致。
3. 教师进入重评与公平处理，选择“两数之和”的“修订为乘积”已发布版本，预览全部范围并创建批次。就绪后查看分差，确认整批激活，成绩应下降为50分，旧成绩快照可通过固定版本API读取。
4. 管理员使用平台管理查看健康、队列、账号和审计。登记影响作业的故障并确认恢复，教师对该事件统一延期或裁决无影响。学生查看通知和新截止。
5. 教师与管理员核对课程归档、申诉保留、到期预览和教师确认。未满180天或存在未决任务/事件/hold时服务拒绝清理。永久数据擦除为单列人工维护审批项。
6. 运行控制支持暂停新提交或新评测派发。应急授权绑定故障影响课程、本人管理员和最多一小时，读取源码和撤销均有审计，普通管理员提交读取仍受限。

## 备份与独立恢复

业务应用和迁移/备份使用独立账号。将私有维护配置中的`ASTRA_DATABASE_URL`加载到当前进程环境，数据库URL不得写入命令行、报告或仓库。

```powershell
pwsh -File tools/database_backup.ps1 -Action backup -File .local/backups/daily.dump
pwsh -File tools/database_backup.ps1 -Action restore -File .local/backups/daily.dump -Target astra_new_restore
pwsh -File tools/database_backup.ps1 -Action inventory -File .local/backups
```

Linux直接运行`python3 tools/database_backup.py`并提供相同参数。要求PostgreSQL16的pg_dump、pg_restore、psql。备份与摘要核验使用同一导出快照，适用于并发写入。恢复只接受不存在的`*_restore`数据库，保留源库，并核对全部表计数及最多100条记录摘要。每日由系统计划任务调用backup，文件名必须唯一。inventory列出超过30天副本，淘汰副本需按留存批准流程执行，脚本不自动删除。

2026-11-03本机已执行一次备份和新库恢复，100条记录摘要一致。运行原始输出保存在忽略目录`.local/course-demo/backup.log`与`restore.log`。恢复目标astra_acceptance_1103_restore保留供交叉核验。

升级使用锁定依赖和`alembic upgrade head`。已有评测、成绩或管理历史的迁移禁止破坏性降级。回滚时先停HTTP受理和Worker派发，保留清理监督，核对最新备份并恢复到新库，确认数据后再切换配置。严禁覆盖当前库或重用未清理的执行槽。

## 独立进程

```text
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8021 --no-access-log
python -m app.modules.judging.worker_cli --enable-execution --executor-host oldali --image sha256:<固定镜像> --executor-state-dir /var/lib/astra-course-executor-demo
python -m app.modules.operations.worker
```

提示Worker由A提供，可信B来源工厂为`app.modules.submissions.sources:build_sources`，显式模型配置、预算与代码外发同意仍由A流程校验。演示初始化未发起收费模型调用。
