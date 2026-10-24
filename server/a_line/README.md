# A线 P1 独立验证与 B 线接入

本目录承载 A 的依赖锁、验证入口及顺序迁移 a001— a004。业务模块在 `server/app/modules`，不导入本目录。它不替代 B 维护的正式应用、shared 层和唯一迁移 head。

## 重现

需要 Python 3.12—3.13、uv 0.13.5、Node 24、pnpm 11.21.0、PostgreSQL 16 和 Playwright Chromium。

```powershell
uv sync --frozen --project server/a_line
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web exec playwright install chromium
$env:ASTRA_A_DATABASE_URL='postgresql+psycopg://<测试用户>:<密码>@127.0.0.1:5432/astra_a_test?connect_timeout=5'
python tools/check_runtime.py
```

数据库名必须以 `_test` 结尾；缺配置会失败。测试为每个用例创建随机 schema，执行真实 Alembic 升级，仅清理自己创建的 schema。浏览器启动显式测试装配 `server/tests/a_line/web_harness.py`，使用虚构账号和合成预检证据，不执行学生程序。测试 HTTPS 证书在 `.local/a-browser-tls`，不提交、不用于部署。CI 使用 PostgreSQL 16 service。

本机此次使用官方 PostgreSQL 16.15 Windows 二进制，回环端口 55433、专用测试库，数据在 Codex tmp 目录；没有把本机路径或 trust 认证要求写入生产配置。Docker 启动未成功，不能声称 Docker 路径已验证。

## 模块与事务接口

| A 提供 | B 集成职责 |
| --- | --- |
| `Identity`：会话、密码、用户管理；`Courses`：课程与成员 | HTTP Cookie/CSRF/Origin、UoW、共享授权与管理页面；身份/课程路由绑定目前见验证 host，集成时迁入 B 总装配 |
| `Problems`：版本、隐藏配对测试、参考程序、完整内容摘要、发布检查 | `PreflightPort` 在同一 UoW 查询预检证据；B enqueue/read HTTP 路由和隔离执行；不在事务锁内调用网络 |
| `Assignments`：草稿/发布、公开题面、截止与提示策略；`admission()` | 提交受理必须在共享锁后调用 admission，使用数据库时间冻结正式性、effective version 和 profile；接入 `AssignmentCoordinationPort` 处理重评互斥与成绩状态 |
| `membership_changed()` | 成员变动或停用账号时，`Effects` 在同一事务调用该写端口递增相关已发布作业 revision/grade_epoch，并更新 B 的成绩依赖 |
| `Learning.resolve()` / `FeedbackSubmissions` | B 终结 attempt 时在同一事务冻结帮助 version_id；查询端口返回已授权的 owner/course/state/verdict/version，不返回源码或执行原始输出 |
| `TeachingIntegrations` / `FixedHelp` 前端接口 | B 启动时注入预检和提交服务、结果组件；结果组件按当前 attempt 读取冻结帮助。默认实现明确报503 |

所有应用服务不 commit。`Repository` 与 `Effects` 必须共享 caller-owned transaction；审计或事件失败须回滚业务、revision 和 epoch。锁顺序固定 policy_guard→课程→作业；验证适配器使用数据库 advisory lock 串行保护，它不构成正式高并发实现或性能证据。

会话查询不续期，作业等自动查询携带 `X-Astra-Background: 1`；B 的预检/结果轮询也须将该信号映射到 `Identity.actor(activity=False)`。普通用户请求续期，空闲15分钟/绝对8小时仍由服务端时间强制执行；客户端标记只能减少续期，不能绕过失效。

正式 B 适配器须替换 `astra_a.storage.SqlRepository`、密码/会话配置与 HTTP 装配，复用业务规则。正式服务应使用按条件分页/有限历史查询的 repository，不应照搬验证适配器“先读取全部可见记录再分页”的实现。代理/多实例的来源限流、审计/outbox、生产连接池与服务监控仍由 B 共同集成。

## 迁移交接

- SQL 快照固定保存在 `migrations/sql/001`—`004` 对应文件中；升级不导入当前 metadata。验证空库→head、a001→a002→a003→a004 带数据升级和重复升级。发布后的题目、材料、作业内容及帮助版本有数据库不可变触发器。
- 正式合入时由 B 将 A DDL 纳入总迁移序列，检查单 head；不能直接再运行一个平行迁移树。A 的版本表名为 `alembic_version_a`，只用于独立验证。
- B 实体尚不可用，`problem_versions.published_preflight_id`、`assignments.active_grade_version/active_rejudge_batch_id` 及 B attempt→feedback_version 的跨线外键须在集成迁移补齐，不能据当前测试宣称跨线引用完整。
- 全局帮助需要已有 ACTIVE ADMIN。显式在管理员初始化事务调用 `seed_global_feedback(repo, admin_id)`；UUID5 固定种子可重复运行，不改写历史或覆盖新 active version。正常应用启动不会建表、建账号或种植合成证据。
- 不提供破坏性 downgrade。独立测试可重建其专用 schema；正式回退必须由 B 按备份/迁移策略审查，不能直接删除数据。

## 契约与未接通边界

验证 host 只注册已经实现的方法，且按 canonical A OpenAPI 校验请求及公开响应。它没有独立推导一份 Pydantic schema，因此这不等于 B FastAPI 导出与 canonical 契约的双向一致性证明。

`GET /problems/{id}/versions`、`GET /problem-profiles` 是页面所需的新增只读方法。profile 由部署注入；无配置时503。这两项 DTO 仍须 B 审查。错误不会回显密码、源码、隐藏数据或驱动报错。固定帮助发布正文按标题+说明+清单总计2000码点/8 KiB 保守校验。

教师保存的 profile 是请求配置，不能直接作为执行端信任来源。B 预检/评测必须在部署允许列表内解析 profile，核实实际安装语言、镜像摘要及资源限制；不得仅信教师 JSON 或按其任意拉取镜像。A 发布检查绑定该配置摘要与 B 预检证据，当前合成测试不证明实际镜像约束成立。

当前只实现 P1-A1—A4。固定帮助编辑/发布页面、模型提示、错题和推荐属于 P2，练习开放策略及完整验收属于后续阶段。预检执行、提交受理、真实评测结果、成绩/重评、审计/outbox、正式生产启动均没有冒充完成。未进行付费模型、隔离攻击、性能、用户验收及 I0/I1 联验。
