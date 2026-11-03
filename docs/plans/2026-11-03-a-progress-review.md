# A线进度复核与题面同步修复

实施A覃锐谦；独立代理审查分别检查已合并预检与待合并学习来源，成员审批不代填。沿用v0.4、FR-05/06/08、BR-07、FR-19/20/21、P3-A2/A3与既有工作流，无新增架构或接口。

## 范围与依据

基线main `674a6d3`，已包含PR6/7/8/9；PR10 `f1b0ba4`仍开放，仅作候选只读审查，不合入B进行中分支。复用A独立工作树与新分支`fix/a/p3-progress-review`。代码修复仅覆盖A题面编辑与重读的一致性；不启动执行器、演示库或收费模型。

## Task 1：题面与服务器修订保持一致

Files：`apps/web/src/features/problems/ProblemPages.tsx`、`VersionMaterials.tsx`、新增`ProblemPages.test.tsx`、`apps/web/e2e-integration/problems.spec.ts`。

接口：继续使用`GET/PATCH /problem-versions/{id}`和既有`VersionMaterials`回调。表单提交仅六项内容字段及expected_revision；服务器元数据不得混入请求。无本地修改时读取最新题面，有修改时保留输入并禁止预检，保存成功后以返回内容为准。材料修订不能静默把旧题面当作已保存。

- [x] 先添加失败用例：外部修订重读后显示新题面；本地编辑跨重读保留并阻止预检；现有版本编辑/复制只提交内容白名单。
- [x] 最小修复共享表单状态，保持页面样式和API不变；独立审查后另补一次成功/下一次断网的回归，移除题面及材料冲突恢复中提前推进revision的重复读取。
- [ ] `pnpm test`、类型/lint/构建及正式浏览器双标签场景通过。浏览器插件未提供，使用仓库Playwright；保存截图、控制台及桌面/窄屏证据。

## Task 2：当前状态与可执行验收交接

Files：`docs/project-status.md`、`docs/a-integration-handoff.md`、`docs/a-user-guide.md`、新增`docs/a-acceptance-checklist.md`及`docs/reports/2026-11-03-a-progress-review.md`。

- [ ] 区分主线已合并、PR10候选、真实执行历史记录和本次复核结果；不修改历史记录。
- [ ] 修订已过期的预检HTTP/迁移说明及作业练习与公开推荐权限边界。
- [ ] 提供空白人工验收记录和A/B衔接用例，人工分数/参与者/恢复结果不代填。
- [ ] 记录重评期间模型来源身份和固定帮助错配的候选发现，明确归属、依赖和无收费验证方法。
- [ ] 文档检查、工具回归、独立审查及当前候选完整检查；按工作流提交，远端交付以实际执行结果记录。

## Review Focus

本地未保存输入不能被后台重读覆盖；新的服务器题面不能配旧表单宣称已保存；模型失败不因文档同步追认为通过；PR10不能误记已合并；公共验收不替B实现其业务。

回退：撤回本批提交即可，不涉及迁移或持久数据。两项任务共享题面行为说明，文档以最终回归为准。
