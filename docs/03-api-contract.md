# 接口契约

## 1. 通用协议

接口前缀 `/api/v1`，UTF-8 JSON，字段使用 snake_case，ID 为 UUID 字符串，时间为 ISO 8601 UTC（毫秒和 `Z`）。下面路径均省略此前缀。资源列表返回 `{items, next_cursor}`，默认 20、最大 100，按稳定字段及 ID 排序；未知游标、字段、枚举拒绝。

认证采用服务端会话与 `HttpOnly; Secure; SameSite=Lax` Cookie，浏览器同源部署。写请求校验 CSRF token 与 Origin；登录也校验 Origin 和预会话 CSRF。GET `/auth/session` 可返回匿名预会话 CSRF，登录后轮换 token。用户、角色从会话取得，写入请求不能覆盖。生产禁止通配凭据 CORS。

A P1 防止轮询续期的接线约定：`GET /auth/session` 只验证、不延长空闲窗口；其他自动 GET 轮询发送可选 `X-Astra-Background: 1`，服务端照常认证授权但不更新 `last_seen_at`。普通用户导航/操作仍可续期；该头不能延长会话或放宽权限。B 预检/结果等轮询接线时遵守同一约定。

响应包含 `X-Request-Id`；客户端 request_id 不可信，格式不符由服务端重写。对源码、成绩、提示、隐藏内容使用 `Cache-Control: no-store`。响应模型按角色白名单投影，不能直接序列化 ORM。

分页、UUID、字段长度违反协议返回 422；JSON/请求头语法错误 400；超 HTTP/源码字节上限 413；身份 401、权限 403、不可见资源 404、业务状态/版本/同键异内容 409、个人限流/额度 429、平台暂不可用 503。所有非 2xx（含 422）统一为：

```json
{
  "code": "STUDENT_PENDING_LIMIT",
  "message": "当前有三个未完成提交，请等待结果。",
  "request_id": "f749974b-46c4-4d5b-a8df-605f9166a85c",
  "retryable": true,
  "retry_after_seconds": 5,
  "field_errors": []
}
```

无重试建议时 `retry_after_seconds=null`；429/可重试 503 同时设置 `Retry-After`。错误信息不含堆栈、SQL、私有路径或隐藏数据。

可编辑聚合与敏感状态迁移提交 `expected_revision`，针对表中明确指定的聚合。多聚合激活分别提交作业和批次 revision。退出/本人改密以当前会话及旧密码验证；提示评价按本人唯一键更新、通知已读/应急授权撤销幂等；新建提交和提示使用各自幂等键。这些命令不要求客户端猜测不存在的 revision。只读或永久内容不更新 revision。重复操作的重放须身份仍有效且对象仍可见；已有成功提交不因新截止/容量再被拒绝。审计理由使用 `reason`，长度 10—500 码点。

## 2. 接口目录

角色标记：S 学生、T 任课教师、M 管理员。表中“本课/本人”必须由服务端验证。请求列列出业务字段，统一分页参数不重复；PATCH 只允许列出的可修改字段。

### 2.1 身份、课程和题目（A 主责，预检 B 主责）

| 方法与路径 | 角色 | 请求 | 成功响应 |
| --- | --- | --- | --- |
| GET /auth/session | 匿名/已登录 | — | 200：authenticated、user 安全摘要或 null、csrf_token、server_time |
| POST /auth/login | 匿名 | login_name、password | 200：user 安全摘要；设置轮换会话 |
| POST /auth/logout | 已登录 | — | 204；撤销当前会话 |
| POST /auth/password | 已登录 | current_password、new_password | 204；撤销所有会话并要求重新登录 |
| GET /courses | S/T | status? | 200：授权课程分页 |
| POST /courses | T | title | 201：course_id、revision |
| GET /courses/{id} | S/T | — | 200：课程安全视图 |
| PATCH /courses/{id} | 本课 T | title、expected_revision | 200：新 revision |
| GET /courses/{id}/members | 本课 T | status? | 200：成员分页 |
| PUT /courses/{id}/members/{user_id} | 本课 T | status、expected_revision | 200：成员状态及课程新 revision |
| GET /courses/{id}/problems | 本课 T | status?、tag? | 200：题目分页 |
| GET /problem-profiles | T | cursor、limit | 200：部署提供的运行环境列表；未配置503，实际隔离由B2核验 |
| GET /problems/{id}/versions | 本课 T | cursor、limit | 200：题目草稿与历史版本分页，含公开内容、不含隐藏测试或参考程序 |
| POST /problems | 本课 T | course_id、canonical_problem_id? | 201：problem_id、家族 ID；未指定则新建家族 |
| POST /problem-versions | 本课 T | problem_id、base_version_id?、题目草稿字段 | 201：version_id、revision |
| GET /problem-versions/{id} | 本课 T | — | 200：维护视图；学生从作业题目接口取公开视图 |
| PATCH /problem-versions/{id} | 本课 T | title、statement、samples、tags、profile、source_ref、expected_revision | 200：草稿新 revision；已发布 409 |
| DELETE /problem-versions/{id} | 本课 T | expected_revision、reason | 204；仅无引用草稿可删除 |
| GET /problem-versions/{id}/testcases | 本课 T | — | 200：草稿/已发布测试明细；含文本，仅教师可读 |
| GET /problem-versions/{id}/references | 本课 T | — | 200：语言及参考源码；仅教师可读 |
| PUT /problem-versions/{id}/testcases/{order} | 本课 T | input_text、answer_text、expected_revision | 200：testcase_id、两份 SHA-256、新 revision |
| DELETE /problem-versions/{id}/testcases/{order} | 本课 T | expected_revision | 204；仅草稿，重新校验连续性 |
| PUT /problem-versions/{id}/references/{language_key} | 本课 T | code、expected_revision | 200：reference_id、checksum、新 revision |
| POST /problem-versions/{id}/preflight | 本课 T | expected_revision | 202：preflight_id、state、content_digest |
| GET /preflights/{id} | 本课 T | — | 200：每语言每样例/隐藏点状态、失败摘要 |
| POST /problem-versions/{id}/publish | 本课 T | expected_revision、preflight_id、reason | 200：published_at、checksum；摘要不符或预检未全通过 409 |
| PATCH /problems/{id}/practice-policy | 本课 T | practice_released、practice_version_id?、canonical_problem_id、expected_revision、reason | 200：策略版本；校验家族归属、活动作业限制 |

题目内容与教学访问策略分离：修改练习开放/家族关联要审计，不改历史题面或评测环境；不允许通过修改家族绕过当前作业提示限制，涉及活动作业的家族重归并拒绝 409，须先结束相关作业。开启练习必须指定属于该题的已发布 practice_version_id；关闭后公开读取立即失效。

### 2.2 作业、提交和成绩（A 作业/编辑器，B 提交/成绩/重评及页面）

| 方法与路径 | 角色 | 请求 | 成功响应 |
| --- | --- | --- | --- |
| GET /courses/{id}/assignments | 本课 S/T | state? | 200：授权分页，未开放仅元数据，不给题面 |
| POST /assignments | 本课 T | course_id、title、items、open_at、due_at、ai_policy | 201：assignment_id、revision |
| PATCH /assignments/{id} | 本课 T | 草稿字段、expected_revision | 200：新 revision；已发布不可用此接口改内容 |
| GET /assignments/{id} | 本课 S/T | — | 200：状态、server_time、items 公开摘要、revision、公平公告、成绩状态 |
| GET /assignments/{id}/problems/{problem_id} | 本课 S/T | — | 200：已开放/截止题目的公开版本、profile、样例；学生不可读未开放题面 |
| POST /assignments/{id}/publish | 本课 T | expected_revision、reason | 200：状态、新 revision；校验题数、总分、时间、自检 |
| PATCH /assignments/{id}/deadline | 本课 T | new_due_at、expected_revision、reason | 200：旧/新截止、新 revision；活动批次 409 |
| PATCH /assignments/{id}/ai-policy | 本课 T | ai_policy、expected_revision、reason | 200：新策略版本；开放后放宽拒绝 |
| POST /submissions | 本课 S | 见第 3 节 | 202：受理回执 |
| GET /submissions/{id} | 本人 S/本课 T | — | 200：安全结果视图 |
| GET /assignments/{id}/submissions | 本人 S/本课 T | problem_id?、student_id?、verdict?、mode? | 200：稳定分页；学生忽略/拒绝非本人筛选 |
| GET /submissions/{id}/attempts | 本人 S/本课 T | — | 200：版本、轮次、状态与指标；无内部 token/隐藏输出 |
| GET /assignments/{id}/grades | 本人 S/本课 T | grade_version? | 200：状态、版本、题分、总分；教师含人数统计 |
| GET /grades/{grade_version} | 本人 S/本课 T | — | 200：该固定快照的授权投影 |
| POST /assignments/{id}/grades/publish | 本课 T | expected_revision、reason | 200：grade_version、published_at；门槛未满足 409 |
| GET /assignments/{id}/grades.csv | 本课 T | grade_version | 200：UTF-8 CSV；列为学生标识、题分、总分、状态、版本 |
| POST /assignments/{id}/rejudge-preview | 本课 T | problem_id、new_version_id、expected_revision | 200：affected_count、range_checksum、版本差异、历史语言集合；不兼容返回409及missing_languages |
| POST /assignments/{id}/rejudge | 本课 T | new_version_id、reason、expected_revision、range_checksum | 202：batch_id、affected_count、state；目标题由新版本所属题目确定 |
| GET /rejudge-batches/{id} | 本课 T | — | 200：范围、进度、失败数、学生分差、revision |
| POST /rejudge-batches/{id}/activate | 本课 T | expected_batch_revision、expected_assignment_revision、reason | 200：grade_version、差异摘要、新 assignment_revision |
| POST /rejudge-batches/{id}/cancel | 本课 T | expected_revision、reason | 200：CANCELLED；停止新派发，正在执行先安全清理 |
| POST /submissions/{id}/retry | M | expected_revision、reason | 202：cycle_id、attempt_id；仅当前 SE |
| POST /rejudge-batches/{id}/retry | M | expected_revision、reason | 202：恢复数量；只重试失败成员，不能遗漏范围 |

### 2.3 学习与通知（A 学习，B 通知）

| 方法与路径 | 角色 | 请求 | 成功响应 |
| --- | --- | --- | --- |
| GET /submissions/{id}/feedback | 本人 S/本课 T | — | 200：feedback_version_id、说明、检查清单 |
| POST /feedback-catalogs | 本课 T/全局 M | scope、course_id?、verdict、language_key、draft | 201：catalog_id、revision |
| PUT /feedback-catalogs/{id}/draft | 所属 T/全局 M | title、explanation、checklist、expected_revision | 200：新 revision |
| POST /feedback-catalogs/{id}/publish | 所属 T/全局 M | expected_revision、reason | 200：version_id、checksum |
| GET /feedback-catalogs/{id}/versions/{version} | 授权 S/T/M | — | 200：固定版本帮助；不读最新草稿 |
| POST /hint-templates | 本课 T/全局 M | scope、course_id?、draft | 201：template_id、revision |
| PUT /hint-templates/{id}/draft | 所属 T/全局 M | body、allowed_placeholders、schema_version、expected_revision | 200：新 revision |
| POST /hint-templates/{id}/publish | 所属 T/全局 M | expected_revision、reason | 200：version_id、checksum；启用前质量回归 |
| GET /hint-templates/{id}/versions/{version} | 所属 T/全局 M | — | 200：模板固定版本；不向学生暴露安全框架 |
| POST /ai-hints | 本人 S | submission_id、question?、data_sharing_consent、request_key | 202：hint_id、PENDING；终态重放 200 |
| GET /ai-hints/{hint_id} | 本人 S/本课 T | — | 200：状态、来源提交、版本、四段提示或降级帮助 |
| POST /ai-hints/{id}/feedback | 本人 S | rating、comment? | 200：USEFUL/NOT_USEFUL/ERROR；每提示本人一条可更新，仅 READY |
| GET /review-items | S | course_id?、context | 200：错题分页；context=FORMAL/PRACTICE |
| GET /recommendations | S | course_id? | 200：最多5个problem_id、practice_version_id、标题及匹配标签 |
| GET /practice-problems/{id} | S | — | 200：指定练习版本的公开题面、样例和profile；按推荐相同规则重验授权/同族，失效404；只读 |
| GET /notifications | 已登录 | unread? | 200：本人通知分页 |
| POST /notifications/{id}/read | 本人 | — | 204；重复已读无副作用 |

帮助正文同时≤8 KiB/2000 码点，检查清单≤10 项；模板正文≤8 KiB，只允许定义的占位符。发布只冻结已校验草稿，不在发布请求夹带新正文。列表和草稿读取补充 `GET /feedback-catalogs`、`GET /feedback-catalogs/{id}/draft`、`GET /hint-templates`、`GET /hint-templates/{id}/draft`，均仅所属教师/全局管理员，返回对应草稿字段和 revision。

### 2.4 管理与运维（B 服务及页面；账号API由A实现）

| 方法与路径 | 角色 | 请求 | 成功响应 |
| --- | --- | --- | --- |
| GET /admin/users | M | login_name?、role?、status? | 200：账号安全分页 |
| POST /admin/users | M | login_name、display_name、role、initial_password、reason | 201：用户安全摘要，must_change_password=true；不回显密码 |
| PATCH /admin/users/{id} | M | display_name?、status?、expected_revision、reason | 200：新 revision；角色变更另经审查不隐含开放 |
| POST /admin/users/{id}/reset-password | M | one_time_password、expected_revision、reason | 204；撤销旧会话，密码不记日志 |
| GET /admin/health | M | — | 200：服务、积压、槽位、磁盘、时钟和模型预算摘要 |
| GET /admin/jobs | M | state?、kind? | 200：失败/等待任务、submission/batch ID及各自revision，无源码 |
| GET /admin/audit-events | M | actor?、action?、from?、to? | 200：只读审计分页 |
| POST /admin/incidents | M | 影响作业、时间、原因、证据引用、证据完整标记、reason | 201：incident_id、revision；用于补记故障 |
| PATCH /admin/incidents/{id}/recovery | M | recovered_at、expected_revision、reason | 200：新 revision；不伪造恢复处理时间 |
| GET /incidents/{id} | 本课 T/M | — | 200：授权事件、范围和裁决摘要 |
| POST /assignments/{id}/fairness-decisions | 本课 T | incident_id、decision、reason、expected_revision | 200：旧/新截止、revision、fairness_review；EXTEND/NO_IMPACT |
| POST /courses/{id}/archive | 本课 T | expected_revision、reason | 200：归档状态；任务/事件未处理完 409 |
| POST /admin/retention/previews | M | course_id、reason | 202：plan_id；服务器生成对象清单，不接收磁盘路径 |
| GET /admin/retention/{id} | M/本课 T | — | 200：清单摘要、到期条件、hold、状态 |
| POST /retention/{id}/confirm | 本课 T | object_digest、reason、expected_revision | 200：教师确认引用 |
| POST /admin/retention/{id}/execute | M | object_digest、confirmation_id、expected_revision、reason | 202：清理任务；执行前重验所有条件 |
| POST /admin/holds | M/本课 T | object_type、object_id、reason | 201：hold_id，授权范围内申诉保护 |
| POST /admin/holds/{id}/close | 原授权 T/M | expected_revision、reason | 200：关闭记录；不绕过其他未决事项 |
| POST /admin/emergency-access | M | incident_id、scope、expires_at、reason | 201：限时授权；读取与撤销均审计 |
| POST /admin/emergency-access/{id}/revoke | M | reason | 204 |
| GET /admin/runtime-config | M | — | 200：脱敏配置和 revision，无密钥 |
| PATCH /admin/runtime-config | M | 允许配置、expected_revision、reason | 200：新配置版本；不可绕过固定资源/业务上限 |

模型配置、价格、模板启用与语言环境采用版本记录和部署流程，`runtime-config` 仅允许启停及引用已验证版本，不能上传可执行命令或任意供应商 URL。`GET /health/live` 公开返回进程存活；`GET /health/ready` 仅反向代理/内部监测访问，详情保留管理员接口。

## 3. 关键载荷

### 3.1 提交

```http
POST /api/v1/submissions
Idempotency-Key: 5419f93a-0b51-464a-9e60-01fa49eb9678
X-Submission-Intent: FORMAL
X-CSRF-Token: <会话令牌>
Content-Type: application/json
```

```json
{
  "assignment_id": "de6c8709-8840-424a-a09a-45cd92abf0d5",
  "problem_id": "1b677a78-47e9-4675-92c5-436bd343092f",
  "language_key": "cpp17",
  "code": "int main() { return 0; }"
}
```

202 回执字段：submission_id、accepted_at、mode、state、request_id。新请求 state=QUEUED。相同键重放仍为 202，返回原受理回执并设置 `Idempotent-Replay: true`；当前结果通过 GET 查询。request_id 标识本次 HTTP 调用，可与原调用不同。摘要包含全部业务字段与 intent，不包含 request_id。

查询响应包含 submission_id、assignment_id、problem_id、original_version_id、effective_version_id、result_basis_id、attempt_id、generation、code、language_key、accepted_at、mode、state、verdict、reason_code、time_ms、memory_bytes、case_results、feedback_version_id、revision。单点仅含 order、verdict、cpu_ms、memory_bytes；指标缺失为 null。原始执行 token、隐藏输入/答案/stdout/stderr、参考程序均不在响应 schema。

### 3.2 成绩

`GradeView={assignment_id, grade_version, assignment_revision, grade_epoch, state, published_at, students}`；学生仅一条本人记录，教师分页读取学生列表。学生记录 `{student_id, total, state, items}`，items 每项 `{problem_id, points, score, target_version_id, source_attempt_id}`。无提交的 source_attempt_id=null。暂定成绩必须显示状态，不能用 published_at=null 的对象冒充已发布快照。

### 3.3 提示

`HintView={hint_id, submission_id, status, reason_code, model_version, template_version_id, sections, fallback_feedback, created_at}`。READY 的 sections 固定为 error_category、location_clues、checks、learning_advice；非 READY 可为 null。费用、供应商原始响应与安全内部规则不返回学生。request_key 按用户唯一，同键异摘要 409。

## 4. 错误码

| HTTP | 主要 code | 行为 |
| --- | --- | --- |
| 400/422 | INVALID_REQUEST、VALIDATION_ERROR、INVALID_PROFILE | 定位字段，不进入执行队列 |
| 401/403/404 | UNAUTHENTICATED、FORBIDDEN、NOT_FOUND | 不泄露不可见对象存在性 |
| 409 | REVISION_CONFLICT、REJUDGE_LANGUAGE_MISMATCH、IDEMPOTENCY_CONFLICT、SUBMISSION_INTENT_MISMATCH、NOT_READY、ACTIVE_REJUDGE、UNRESOLVED_FAIRNESS | 重新读取状态；不能无条件循环重试 |
| 413 | CODE_TOO_LARGE、FILE_TOO_LARGE、CONTEXT_TOO_LARGE | 保留输入并显示字节上限 |
| 429 | STUDENT_INTERVAL、STUDENT_PENDING_LIMIT、AI_DAILY_QUOTA、AI_USER_PENDING | 个人限制；平台积压致名额占满仍登记公平审查 |
| 503 | GLOBAL_CAPACITY、JUDGE_UNAVAILABLE、PERSISTENCE_UNAVAILABLE、CLOCK_UNHEALTHY、STORAGE_FULL、AI_BUDGET_EXHAUSTED、AI_UNAVAILABLE | 明确平台原因；提示失败不影响评测；符合条件时登记公平事件 |

## 5. 内部端口

| 端口 | 输入输出 | 失败语义 |
| --- | --- | --- |
| PreflightPort.enqueue/read | version_id、content_digest、profile → 预检ID及不可变结果 | judging负责执行，problems核验摘要后发布；不在请求事务中执行程序 |
| JudgePort.create_case | attempt_id、generation、lease_epoch、testcase_order、代码、单点输入、language/profile 冻结配置 → ticket | 超时不确定创建记 CREATE_UNKNOWN；token 仅内部保存 |
| JudgePort.poll_case | ticket → phase、backend_status、exit_code、原始输出、cpu_ms、memory_bytes、resource_reason | 传输/执行器/文件故障→SE；明确资源证据才映射 TLE/RE |
| JudgePort.cancel_and_cleanup | ticket/lease → 已停止及目录清理证明 | 未确认隔离槽位，不立即复用 |
| ModelPort.generate | 公开上下文、模板版本、模型版本、token 上限 → 四段候选、usage、供应商请求 ID | 超时、限流、非法 JSON、安全拦截分别留码；费用未知不能记 0 |
| ClockPort.now | 数据库真实当前时刻 | 不能回退为客户端时间 |
| AuditPort.append / EventPort.append | 不含敏感正文的事件 | 与敏感业务变更同事务；审计写失败则敏感写回滚 |

Judge0 的原生状态、language_id 与默认比较规则不直接暴露为产品契约。适配映射必须用实际部署版本验证。

## 6. 契约管理

P0 将本文件全部路由落实为 `specs/openapi.yaml`（OpenAPI 3.1），每条包含请求、角色、安全响应、所有状态码及示例。FastAPI 导出与该文件做语义差异检查，前端生成类型/客户端；后端、Mock 和测试共享 schema。实现前先合并契约变更；删除字段、改类型/枚举/错误语义属于不兼容变更，须同步两个路线并迁移客户端。
