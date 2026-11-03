# A 线独立能力与 B 接线交接

范围：P0-A4、P2-A2/A3、P3-A2/A3 的 A 独立交付材料。B 继续负责预检执行、提交评测、结果/历史、成绩/重评与公平服务及其页面。本文件是当前代码接口清单，不能视作 B 成员审批、I0/I1/I2/I3 完成或生产启用证明。最终分支 SHA、命令及实测结果由[项目状态](project-status.md)和本次交付记录登记。

## 1. 当前装配及数据边界

正式 HTTP 入口为 `server/app/main.py:create_app`，共享 B 的 `SqlRepository`、`UnitOfWork` 和 `TransactionalEffects`。迁移单链为 b006预检→b007模板→b008提示；不要重新分叉历史迁移。启动不建库、不创建账号、不插入模拟提交。前端生成类型来自 `specs/openapi.yaml`，API 统一前缀 `/api/v1`。

`create_app` 接受 `learning_results`、`hint_sources`、`hint_configuration`。默认没有 B 来源，相关接口明确503；本批模型运行配置及独立 Worker 的最终命令见[服务端说明](../server/README.md)，配置ID必须与 HTTP/Worker一致。模型凭据仅服务端按环境变量引用读取，不传入浏览器、数据库或普通日志。

自动 GET/轮询发送 `X-Astra-Background: 1`，不延长交互活跃期。写操作沿用同源 HTTPS Cookie、Origin、CSRF、统一错误和请求编号；禁止将后台轮询伪装成用户操作来维持会话。

## 2. 集成矩阵

| 连接点 | A 提供/消费的精确接口 | B 需要提供的行为 | 联验断言与当前边界 |
| --- | --- | --- | --- |
| 模型提示来源 | `hint_service.Sources` 继承 `policy_rules.HintSources`；`hint_source(repo, student_id, submission_id) -> HintSource | None` | 在调用者当前事务重新确认来源可见性、归属、练习公开状态，返回 submission_id/student_id/course_id/problem_id/state/verdict/feedback_version_id | state为FINISHED，verdict为CE/WA/TLE/RE；固定帮助指向该轮冻结版本。跨账号/跨课/停用/撤销公开均拒绝，不能用合成提交填生产空缺 |
| 模型上下文 | `hint_context(repo, source) -> Record`；`model_worker.prepare_context` 处理上下文 | 只返回允许外发的公开题面/样例、本人代码、净化诊断；结构与 `prepare_context` 同步 | 不传隐藏输入、答案、参考代码、密钥或其他学生信息。先授权再读取；读取后复验来源未变，网络调用发生在事务外 |
| 学习结果投影 | `student.LearningResults.projection(repo, actor) -> Select[Any]`，注入 `create_app(learning_results=...)` | 只读SQL列：user_id、submission_id、assignment_id、problem_id、version_id、accepted_at、context(FORMAL/PRACTICE)、verdict、effective(bool) | 保留历史学生错误，仅当前有效AC标effective；不得混入源码/测试/诊断/分数。A加入当前成员、作业和发布版本过滤，稳定排序、先授权再推荐前5题 |
| 错题/推荐 HTTP | `GET /review-items?context=FORMAL\|PRACTICE&course_id=...&cursor=...`；`GET /recommendations?course_id=...`；`GET /practice-problems/{id}` | 提供上述投影并在重评/激活时更新有效语义 | SE不算错题；练习与正式分开；同族限制及公开版本复验。来源缺失为503而非空列表。公开题面路由不代表练习受理已接入 |
| 教师预检 UI | `configureTeachingIntegrations({preflight:{enqueue(versionId, revision), read(id)}, submissions, ResultPanel})`；`Preflight`字段 preflight_id/state/content_digest/summary? | B 在应用组合处注入 transport，state映射QUEUED/RUNNING/PASSED/FAILED，轮询保留background语义 | A每2秒读未终态；修订改变后旧预检失效。题目发布仍由 `POST /problem-versions/{id}/publish` 校验 expected_revision/preflight_id/reason。当前总契约尚无预检HTTP路径，不在A臆造URL |
| 提交 transport | `submissions.send(Readonly<SubmissionIntent>) -> Promise<SubmissionReceipt>` | 接收 idempotency_key/assignment_id/problem_id/language_key/code/code_sha256/intent；返回 submission_id/mode/accepted_at，由服务端决定正式性 | 未知受理保留同键原快照；同键异内容拒绝；截止跨越按B规则。默认503，不模拟成功；当前总契约尚无提交受理HTTP路径 |
| 结果组件 | `ResultPanel?: ComponentType<{submissionId: string; onClose: () => void}>`，编辑器以受理回执ID挂载 | B 自行实现结果、历史、轮次、成绩、重评及错误/空态；关闭后回到编辑器 | 切换submission/attempt清除旧结果和帮助；不展示上一轮/他人数据。可引导 `/learning?submission_id=...#learning-hints`，仍由后端授权 |
| 冻结固定帮助 | `GET /submissions/{id}/feedback`；`FixedHelp`组件消费返回的 `FeedbackVersion` | B 结果轮次绑定冻结feedback_version_id，从接口取本轮授权帮助再嵌入；不得读“最新帮助”替代历史版本 | 切轮次清空旧帮助；未完成判定不编造固定帮助；安全Markdown，不暴露隐藏测试。当前A浏览器仅测试组件宿主，不算B结果页联验 |
| 提示 HTTP | `POST /ai-hints`；`GET /ai-hints`；`GET /ai-hints/{hint_id}`；`POST /ai-hints/{id}/feedback` | B 来源可用后与A装配同配置；请求含 submission_id/request_key/data_sharing_consent/question? | 接纳202或同键已有结果200；读取重新授权；PENDING/READY/FAILED/BLOCKED及冻结降级明确；错误不影响评测/成绩 |
| 公平/重评展示 | A作业页直接展示 AssignmentView 的 `fairness_review`（PENDING/RESOLVED）与非空 `fairness_notice`；暂无重评状态接口/插槽 | B 提供当前授权的真实复核状态和公告，完成裁决事务；重评进度组件、状态及路由契约另行约定 | 当前公告按纯文本显示，空态不留空面板。前端契约样例只证明显示，不证明B裁决流程；B发布/重评/公平事务规则及真实公告联验仍待B完成 |

`hint_context` 必需字段为 `public_problem`、`student_code`、`language_key`、`sanitized_diagnostic`、`verdict`、`public_samples`，每个公开样例含 `input`/`output`。`prepare_context` 添加 `schema_version="1"` 与学生 `question`，限制以 `server/app/modules/learning/model_worker.py` 为准。适配前共同核对测试夹具和严格校验，不将任意 B record 原样外发。接口拓展先更新契约和生成客户端，不手改 `schema.d.ts`。

## 3. 联调次序与证据

1. 核对最新 main、A/B分支及本地未推送依赖；B确认来源适配器和总契约。保持B进行中分支独立，不为演示直接合入。
2. 在独立 `_test` 数据库运行单链空库/升级迁移，组装正式HTTP；先测真实来源的停用、跨账号、跨课、同族、公开撤销和重评有效性，再接页面。测试夹具不能进入正式装配。
3. B注入预检/提交/结果组件，执行教师建课→版本材料→真实两语言预检→发布作业→学生草稿→受理→真实判定→冻结帮助→成绩。保留同键并发、响应丢失、跨截止、旧预检失效及切轮次证据。
4. 接学习投影及 Sources，用同一提交验证错题、推荐、固定帮助、提示权限；策略在排队/外发/生成/读取之间变化均拦截。Worker网络调用不得持有数据库事务；重启未知费用保留预占，不自动重发收费请求。
5. 完成B公平公告/重评状态后，在A相关页面复验可见性和理解路径，再执行I1/I2。跨线结果以真实当前候选记录；独立规则、替身模型、真实小额模型调用、人工质量和整站联调分别计数。

## 4. 可复用检查与未完成验收

前端已有 `e2e-integration`：identity、problems、assignments、editor-recovery、feedback、templates、student-learning、learning。`playwright.server.config.ts`使用正式应用与独立schema（8012、HTTPS4175）；`playwright.integration.config.ts`使用A独立harness（8011、HTTPS4175），两者不能同时占端口。Mock基础检查使用4173，生产产物检查4174。默认项目中的 desktop/wide/mobile 都是 Chromium视口，不能据项目名声称跨浏览器。

正式浏览器从仓库锁定环境提供 `ASTRA_SERVER_PYTHON` 与 `ASTRA_TEST_DATABASE_URL`，在 `apps/web` 执行 `pnpm e2e:server`。全量验收仍统一执行 `python tools/check_runtime.py`，目标浏览器检查不替代完整入口。自动化工厂为虚构账号/题目，只能证明被测分支与断言，不证明生产、模型语义或真实参与者可用性。

| 待办 | 负责人/参加者 | 必留证据 |
| --- | --- | --- |
| 真实模型首轮30例与人工D/A/S | A组织，A/B实际独立评分 | 冻结输入/预期/版本/哈希、首次全结果和失败、两份评分及分歧复核；D≥24/30、A≥27/30且S全通过；费用/延迟单列 |
| 5名非开发者可用性 | A组织；真实教师/学生代表 | 参与者匿名编号、非开发者属性、设备/浏览器、任务耗时/成功/误解、问题等级及复测，不以代理执行充数 |
| 跨浏览器/键盘/窄屏 | A/B各自页面 | 实际浏览器版本、1366×768及390×844等尺寸、键盘焦点/弹窗/编辑器、空态/错误、截图/console；Playwright WebKit不等同真实Safari |
| B 来源与公平/结果接线 | B实施，A检查连接处 | 实际来源无替身、权限/版本/重评/公告、端到端断言、当前SHA |
| 独立恢复及课程容器 | B组织，A按手册交叉执行 | 两语言正常/错误/超时、禁网/资源/清理及完整恢复对账；可选高规格/攻击诊断不与课程门槛混记 |
| 成员评审/合入/集成回归 | 实际成员及发起人授权范围 | 不代填B批准；代理审查明确标记；保护规则和当前候选检查、CI分别核对 |

## 5. 2026-11-03 A 页面独立检查

在本批A功能分支、正式HTTP测试harness与独立PostgreSQL schema上，使用项目Playwright（Browser插件未提供），检查 `https://localhost:4175`。视口1366×768、390×844；移动视口是桌面引擎模拟，不是真实手机验收。

- Chromium 156.0.8078.4：上述7份目标spec共24项全部通过，命令退出0。覆盖课程/成员、题目材料、作业/草稿/不可用提交、固定帮助、模板恢复、学习来源不可用、标明替身的学习展示及公平公告契约样例。
- WebKit 27.2：相同22项既有检查通过；新增公平公告2项在单独最终命令通过。最初新用例的自然Tab发现断言失败，最小anchor/button HTML同样跳过链接；最终仅在WebKit显式聚焦跳转链接后用Enter验证激活，不能据此声称WebKit原生Tab发现已通过。实际Safari仍待真实设备验证。
- Firefox 157.0：已安装但Windows原生启动提示“应用程序的并行配置不正确”，Playwright为`spawn UNKNOWN`；未进入页面，不计跨浏览器通过，也未修改系统运行库。
- 公平公告从PENDING→RESOLVED→NONE，纯文本HTML、100字符无断点内容、窄屏无横向溢出、空区域隐藏均验证。最终新用例检查标题/URL、有内容、无Vite错误层、console warning/error与pageerror为空；桌面/窄屏截图已查看。Chromium验证自然Tab→跳转链接→Enter→main焦点。

`AssignmentActions.test.tsx`先观察2项缺公告区域失败，再实现展示；最终该文件5项通过。类型检查及修改文件ESLint/Prettier通过。新用例中的公平内容、READY提示和错题列表按名称明确标为前端契约样例，不证明B真实来源或裁决。测试原始产物位于本机临时目录 `astra-a-ui-20261103`，最终报告和截图另复制到工作区忽略目录 `.local/a-live-ui`，最终Chromium和WebKit公平专项保留JSON报告及截图；最终交付SHA与全量检查由本次交付记录补齐。

5名非开发者、实际A/B模型评分、B真实来源/结果/预检/公平/重评联调及课程环境恢复仍待完成；未完成项不因写出步骤或自动化通过而计为验收。
