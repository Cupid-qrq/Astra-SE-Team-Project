# 课程单槽容器冒烟

本目录落实v0.4的基础容器准备，支持低资源Linux测试宿主。它只运行控制脚本内公开合成夹具，不能接收学生程序，不是JudgePort/Worker服务，也不自动启用正式评测。旧独立VM登记及V系列攻击诊断保留为可选；不需要四槽规格才能运行本检查。

## 环境与镜像

从宿主系统签名源安装Podman；不启用socket/API服务，不开放端口，不修改防火墙。镜像依据[阿里云官方基础镜像说明](https://www.alibabacloud.com/help/en/alinux/getting-started/use-an-alibaba-cloud-linux-image-in-docker)，Containerfile固定基础digest，构建联网更新签名系统包并安装gcc-c++、python3。最终执行必须使用该次构建的不可变镜像ID，不能使用可变tag。重建更新包可能产生不同ID，须重新冒烟并保留实际版本；不是逐字节可重现构建。

在Linux仓库根目录准备：

```bash
sudo dnf -y --setopt=install_weak_deps=False --setopt=gpgcheck=True install podman
sudo podman pull alibaba-cloud-linux-3-registry.cn-hangzhou.cr.aliyuncs.com/alinux3/alinux3@sha256:fd25a109fcbd1ff33692ac32e1890c986fe7b4b656ab54a27a69aba04b8360c7
sudo podman build --pull=never -t localhost/astra-course-smoke:local -f infra/judge/course/Containerfile infra/judge/course
sudo podman image inspect localhost/astra-course-smoke:local --format '{{.Id}}'
```

把输出补成`sha256:<64位ID>`，在下一步使用。基础镜像pull与构建是可信环境准备；测试程序的编译和运行始终禁网。

## 执行与清理

```bash
sudo python3 tools/course_container_smoke.py --image sha256:<实际镜像ID> --source-sha <当前仓库基线40位SHA>
```

宿主脚本兼容Python3.6，无额外依赖。业务服务Python要求不变。`source_sha`记录调用者提供的仓库基线，`controller_sha256`绑定实际传到服务器的脚本内容；报告必须同时保存两者并核对，不能只拿基线号证明未提交脚本一致。

每次持锁启动前检查本工具标签的遗留容器/卷，存在或查询状态未知即拒绝运行；即使控制进程遭SIGKILL而来不及写隔离标记，也不能复用。每次只有一个测试槽，两个语言各做正常求和、编译阶段错误和墙钟超时。配置依据[Podman运行参数](https://docs.podman.io/en/v4.9.3/markdown/podman-run.1.html)与[卷参数](https://docs.podman.io/en/v4.9.3/markdown/podman-volume-create.1.html)：非root、只读根、无额外临时目录、禁网、移除能力、禁止提权，单工作tmpfs卷32MiB；编译512MiB/30实体/20秒，运行256MiB/1实体，C++CPU2秒/墙钟5秒、PythonCPU4秒/墙钟10秒，单文件及合并stdout/stderr均限1MiB。工作卷以受限sleep容器保持挂载，避免编译退出时tmpfs数据丢失；整个用例结束再删除。宿主不挂载业务目录、秘密或Podman/Docker socket。

脚本核对实际inspect配置，控制总轮次360秒；正常/异常均停止并确认容器退出后删除卷。Podman客户端的退出码与容器退出码分开；超时后的退出由清理确认，不能把客户端退出当容器结束。无法确认清理时结果失败，并写`/run/astra-course-smoke.blocked`，后续拒绝复用槽。管理员只检查报告`resource_prefix`对应、标签一致的三个容器和一个卷，确认退出与删除后才可移除该隔离标记。禁止全局prune或删除其他任务资源。

输出为`astra-course-container-smoke-v1` JSON，退出0才表示六项符合预期且清理确认；错误/未知返回非零。报告不含原始程序输入输出、源码或凭据，未知CPU/内存测量为null。本检查不声称完成攻击探针、忙循环CPU/内存压力实测、业务任务恢复、成绩验收或完整NFR验收；这些须分别按实际开发阶段检查。

本机/CI只执行离线控制边界回归，不SSH、不运行学生代码：

```bash
python -m unittest discover -s tools/tests -p test_course_container_smoke.py -v
```


## 课程执行接口（Worker候选）

`tools/course_executor.py`和`course_runtime.py`复用冒烟工具的Podman限制，供独立Worker经固定SSH命令调用，JSON仅经stdin/stdout私有通道传输。需将三个脚本放在受控目录，保持字节一致；宿主为已验证cgroup v1 Linux，SSH已知主机校验开启。默认状态目录/var/lib/astra-course-executor为私有目录，journal只保存身份、摘要和私有结果，不保存输入源码；结果不是普通日志，部署须按留存规则清理。容器仅挂载本次tmpfs工作卷，不能访问状态目录或控制socket。

命令：`python3 /opt/astra-course-test/course_executor.py --image sha256:<已验证镜像ID>`。execute请求字段operation、execution_id（64位摘要）、request_hash、image、language、code/base64、stdin/base64；cancel只传operation与execution_id。身份在创建前fsync，STARTED未完成记录不重跑，取消先写持久fence再清理。单槽文件锁覆盖操作；取消遇到运行锁忙时不声称清理完成，调用者保留数据库槽并稍后恢复。执行异常或不确定清理返回安全SE，不回显原始异常。

运行CPU统计使用独立父cgroup累计用量且排除conmon，保持原RLIMIT_CPU C++2秒/Python4秒；退出后读取真实CPU用量判断TLE，再清理所有空父组。未知内存指标为null；cgroup v2尚未验证，会拒绝执行，不伪装兼容。输出合计限1MiB，返回正文只供服务端比较，非授权API/报告不得转发。编译20秒、运行墙钟5/10秒、单实体等限制继续执行。

`app.adapters.course_executor.CourseExecutor`固定主机别名、镜像和远端脚本路径，禁止把源码拼接进命令；传输限时/限长，状态校验失败不接受成功结果。必须在数据库事务外调用execute/cancel。当前阶段不自动启动Worker或启用学生接口；后续账本接线需以数据库租约保护领取及回写。
