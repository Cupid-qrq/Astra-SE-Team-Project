# A 线版本化固定帮助实施计划

> 执行方式：按 `executing-plans` 在当前 A 独立检出逐项实施；先观察失败，再实现，通过后提交；末尾独立代理审查。任务状态以本文件与项目状态为准。

**目标：**交付 P2-A1 中 FR-19 固定帮助的维护闭环，教师管理本课、管理员管理全局；学生及历史评测始终读取冻结版本。

**基线：**已审定规划 v0.3，main `822687c`；A P1 已随 `ec3fb0b` 合并，B 正式应用、事务、迁移及评测准备已合并。实施 A覃锐谦，成员评审 B祝祎帆；代理审查不替代成员审批。

**设计依据：**[需求 FR-19](../01-requirements.md)、[学习 API](../03-api-contract.md)、[版本与冻结引用](../04-data-design.md)、[教师维护页](../05-ui-specification.md)、[工作流](../../CONTRIBUTING.md)。I1 尚未完成，本批为可独立验证的增量，不宣称 P2/I1 验收。

**架构：**复用 learning 目录/草稿/不可变版本表和 B 的正式 UoW、Repository、Effects。实现已约定的五个维护方法；增加管理用历史分页读取及向后兼容的草稿元数据，旧公开版本响应不变。UI 沿用现有令牌、表单、确认框与安全 Markdown，无需更换栈或重新设计。

**技术栈：**React/TypeScript/TanStack Query、FastAPI、SQLAlchemy/PostgreSQL、现有依赖锁。

## 约束与审查重点

- 教师只能维护自己的课程；管理员只管理全局，不能借该入口读取课程草稿。学生不能读草稿、列表和管理历史。
- 全局帮助仅允许 ALL；课程支持 ALL/cpp17/python3。自然键重复明确 409；归档课程可读，不可写。
- guard→课程→目录锁序；保存与发布均检查并递增 draft_revision。发布只冻结已保存草稿，正文/理由不允许随确认漂移。
- 正文总计最多 2000 码点/8192 字节、清单最多 10 项；敏感操作理由 10—500 码点。公开固定版本保持既有安全投影。
- 版本与有效指针、revision、审计/Outbox 一次提交；失败全回滚。新发布不改旧版本与旧 attempt 引用。
- 正式列表和历史先 SQL 授权/过滤，再 limit+1 签名游标分页。游标不能跨身份、课程或目录复用。
- 401/409/503 和后台刷新均保留当前编辑内容；冲突明确重新核对，不自动替换 revision 重试。预览沿用 SafeMarkdown。
- 不调用模型、执行学生代码、改写历史迁移、合并 main 或代填 B 成员审批。

## Task 1：服务、契约及真实数据库回归

文件：`server/app/modules/learning/{application,feedback,api}.py`、`server/app/api/lists.py`、`server/app/shared/effects.py`、`specs/openapi/a.openapi.json`、`specs/openapi.yaml`、`apps/web/src/lib/api/schema.d.ts`；测试 `server/tests/a_line/test_feedback_management.py`、`server/tests/shared/test_feedback_management.py`。正文校验复用既有 domain。

接口：消费现有 Repository/Effects；提供 list/create/draft/save/publish 及 `GET /feedback-catalogs/{id}/versions`。草稿增加可选的 scope/course_id/verdict/language_key/active_version_id/active_version_no/course_status；历史只供管理者返回 version_id/version_no/title/checksum/published_at。现有固定版本查询与 resolve 保持签名。

- [x] RED：HTTP 创建→保存→发布→第二版→第一版仍不变；学生/他课/管理员越界、归档、重复键、超长正文、过期 revision、夹带发布正文失败。
- [x] GREEN：最小实现；审计失败不留下目录/版本/有效指针；双连接同 revision 只有一次发布生效。
- [x] 正式 HTTP/UoW 验证同一流程和授权分页；检查新旧契约映射、前端生成类型一致。
- [x] 验证：两组 pytest、ruff/mypy、`tools/check_api_contract.py`、`pnpm contracts:check`。通过后中文提交。

## Task 2：课程与全局维护页面

文件：`apps/web/src/features/learning/Feedback{Pages,Editor}.tsx`、`feedbackDrafts.ts`、`client.ts`、`App.tsx`、`CoursePage.tsx`、必要样式；测试 `Feedback{Editor,Pages}.test.tsx`、`e2e-integration/feedback.spec.ts`。

接口：使用 Task 1 生成类型和现有 CSRF 客户端；教师 `/teacher/feedback`，管理员 `/admin/feedback`；详情子路由按 catalog_id 隔离表单与查询缓存。

- [x] RED：教师课程入口、创建、编辑草稿、预览、安全渲染、带理由确认发布、历史版本选择；学生和管理员边界。
- [x] GREEN：列表/加载更多、明确草稿与生效版、保存后才可发布、确认冻结 revision/理由、错误不丢内容、归档只读。
- [x] 真实 PostgreSQL 下运行 A 验证 host 和 B 正式应用的三视口浏览器；核对移动溢出、键盘与截图，页面运行错误有断言；浏览器控制台未逐项单独采集，不冒称完整控制台审计。
- [x] 验证：前端 lint/typecheck/unit/build/contracts，浏览器目标流程。通过后中文提交。

## Task 3：整分支验证、审查与交接

- [x] `python tools/check_runtime.py` 在修复提交 `8a2516e` 退出0；收尾文档更新后仓库1057项无错误、工具19项通过及差异检查通过。浏览器71项通过，另12项既有跳过；未验收边界见报告。
- [x] 使用 requesting-code-review 派发一次整分支独立审查；重要问题 RED→GREEN 修复并回归，不代填 B 合并审批。
- [x] 更新 `docs/project-status.md`、服务/契约说明和[本批报告](../reports/2026-11-02-a-versioned-help.md)，记录代码 SHA、命令、数量、增量契约及 B 待审事项。
- [x] 已 fetch 核对最新主线 `822687c` 被当前分支包含，双方未推送依赖仍待成员明确确认；本地提交可评审产物，保留分支和工作区，未执行推送/PR/合并。

**回退：**撤销本功能提交即可；没有新增/重写迁移。已发布版本继续受数据库不可变约束保护，回退后原固定版本读取照常；停止新增维护操作不会改历史评测引用。
