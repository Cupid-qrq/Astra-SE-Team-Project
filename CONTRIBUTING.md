# 开发工作流

## 1. 环境与任务入口

两位开发者都必须在自己的Codex启用[Superpowers](https://github.com/obra/superpowers)和[Build Web Apps](https://chatgpt.com/plugins/build-web-apps?open_in_app)。首次开发记录插件版本、已加载能力和一个实际检查结果。仅安装在另一人的机器上不算完成；工具不可用时登记阻塞，可继续不依赖它的工作。

每个任务登记阶段ID、负责人、评审人、关联FR/NFR、文件范围、依赖及验收方法。先读取README、对应规范和AGENTS，核对本地改动归属，再开始工作。当前项目状态只维护在[项目状态](docs/project-status.md)，不混入长期规范。

## 2. Superpowers与Build Web Apps的执行流程

| 环节 | 必须执行的流程 | 产物与退出条件 |
| --- | --- | --- |
| 设计 | Superpowers `brainstorming`：辨明目的、现状、边界和取舍；既有需求充分时不重复询问 | 新架构/接口变更形成设计说明，经另一成员确认；已有批准设计的修复定位到具体规则 |
| 计划 | `writing-plans`：任务拆到可独立验收，列实际文件、输入输出、测试和依赖 | 任务计划保存于 `docs/plans/`；一个任务一个负责人；引用总规范，不复制全文 |
| 隔离 | `using-git-worktrees`：检查现有分支及工作区；已有适合检出可复用 | 每人独立检出；共享文件先协调，禁止覆盖对方改动 |
| 实现 | `executing-plans`按任务推进；明确需要独立并行子任务时可选`subagent-driven-development` | 业务规则先失败测试→最小实现→通过→整理；使用`test-driven-development`，不是先写实现再补同形测试 |
| 页面 | Build Web Apps的Frontend App Builder、React Best Practices及适用的组件能力 | A维护统一组件；A/B各自使用相关能力实现、调试和验证所属页面；遵循UI规范，不引入无关支付或托管依赖 |
| 数据 | 两人核对接口、迁移、事务、索引；Build Web Apps的Postgres相关能力仅用于适用的设计检查 | PostgreSQL仍由本项目管理；不能因插件包含Supabase而改换架构 |
| 调试 | Superpowers `systematic-debugging`先复现和定位原因；页面问题同时使用Build Web Apps的Frontend Testing Debugging | 保存最小失败用例，修复后回归；不能连续猜测式修改 |
| 审查 | `requesting-code-review`提供精确任务/文件/变更范围；`receiving-code-review`核实反馈后修正 | 独立检查规范符合性、边界和代码质量；代理审查不替代另一位成员的合并审批 |
| 验证 | `verification-before-completion`运行当前修改对应的完整检查；页面必须真实浏览器操作 | 保存命令、结果、commit、环境与必要产物；未执行项不得写通过 |
| 收尾 | `finishing-a-development-branch`核对检查、审查、未推送依赖和集成方式 | 按本文件的推送/合并步骤完成；清理仅限已结束且无依赖的分支/工作树 |

纯文档修订执行文档检查和独立内容审查，不为排版制造业务测试。插件流程服务于任务，不保存提示词流水或重复设计文档。Build Web Apps能力以[官方插件页](https://chatgpt.com/plugins/build-web-apps?open_in_app)和当前已加载技能为准，不能声称使用过不可用能力。

每次新功能的实现计划至少包含：引用的需求、修改文件、提供/消费的接口、失败用例及断言、验证命令、预期结果和回退方法。阶段总计划不扩写成全部函数实现；具体任务开工前补齐文件级计划，经另一人审查后实施。

## 3. 分支与开发节奏

`main`为可集成主线。分支使用`feat|fix|refactor|test|docs|chore/<a|b>/<阶段-主题>`，例如`feat/b/p2-rejudge`。功能分支原则上不超过3个工作日；超过时拆成兼容的小PR。两人每周至少两次集成。

```powershell
# 工作区干净且无他人未提交改动后执行
git fetch origin --prune
git switch main
git pull --ff-only origin main
git switch -c feat/a/p1-course-members
```

禁止直接推main、无条件强推、共享分支rebase和覆盖他人文件。个人已推分支优先merge最新main；确需改写个人历史时先确认无人依赖，再限用force-with-lease。用户明确禁止推送的任务不运行任何push或远程写操作。

## 4. 中文commit

格式：`（开发者标识及姓名）类型(可选范围): 中文说明`。固定身份为`A覃锐谦`、`B祝祎帆`，前缀使用中文全角括号；类型为feat、fix、refactor、test、docs、style、perf、build、ci、chore、revert；类型后的冒号接受半角或全角。标题说明及正文主要用中文，技术标识保留原文。

```text
（A覃锐谦）feat: 开发实现课程成员停用与历史保留
（B祝祎帆）fix(judging): 修复过期租约结果覆盖当前轮次的问题
（B祝祎帆）test(grades): 补充重评降分与整批激活回归测试
```

署名使用实际提交者的固定身份，与Git author姓名和本人已验证邮箱相符；接手另一条路线的任务也不能冒用对方姓名。结对时由主提交者署名，正文说明双方贡献；需要Co-authored-by时使用双方真实邮箱。合并commit及Squash最终标题同样带署名；不自动使用英文默认合并标题。脚本校验身份组合及中文说明，Git作者信息与实际贡献由同伴审查。

说明写清行为、对象和原因，不能只写“更新”或“修复问题”。一次commit只包含一个逻辑改动；明确路径暂存，检查`git diff --cached`。新标题由`python tools/check_commits.py --base origin/main --head HEAD`检查，正文及含义由评审人核对；不改写历史英文提交。

## 5. 检查与CI

规划阶段运行`python tools/check_repository.py`、`python -m unittest discover -s tools/tests -v`和`git diff --check -- . ':(exclude)archive/submissions/**'`。归档原件另由白名单、SHA-256和ZIP一致性检查验证，不对其换行做格式化。P0第一份工程PR必须同时提交该工程的真实验证命令；后续按引入的能力补充验证，不要求空工程运行尚不存在的功能测试。

| 能力进入仓库时 | 同一PR必须具备的检查 |
| --- | --- |
| 前端工程 | 依赖锁、lint、类型、单元、生产构建、最小浏览器冒烟 |
| API/数据库工程 | 依赖锁、格式/类型、单元、真实PostgreSQL集成、空库迁移 |
| 对外API | OpenAPI契约、生成客户端一致性、权限与错误响应 |
| 评测/成绩/提示等业务 | 对应规则边界、并发/故障回归和浏览器集成 |
| 数据迁移或发布 | 空库/上版升级、受影响数据对账、兼容/回滚及适用脚本自检；完整独立恢复按质量文档的P3及相关变更门槛执行 |

B在P0建立唯一入口`tools/check_all.ps1`，在独立PowerShell进程执行并返回明确非零失败码；CI与本地均经`python tools/check_runtime.py`实际调用同一入口，不能仅检查它存在。PR默认检出与目标分支的合并候选运行检查；提交标题仍核查真实PR提交区间。CI的运行环境/数据库由P0工程PR一起配置。入口不得用空脚本、echo或跳过用例伪装通过。所需命令和测试内容由另一成员审查，机器检查不替代这一步。

## 6. 推送前同步与检查

提交完成后执行：

```powershell
git status --short --branch
git fetch origin --prune
git rev-list --left-right --count origin/main...HEAD
git diff --stat origin/main...HEAD
pwsh -File tools/pre_push.ps1
```

预检要求工作区干净、工作分支合法、fetch URL及实际push URL均为正式仓库、最新`origin/main`已纳入HEAD、远端同名分支没有本地遗漏的提交；随后执行仓库、commit和已建立的完整工程检查。预检自身不push。

上面计数的left必须为0；否则先执行`git merge origin/main -m "（A覃锐谦）chore: 合并最新主线并验证集成"`，其中示例按实际执行者替换为A或B的固定身份，解决冲突后重新检查。检查通过且获准推送后，使用`git push -u origin <当前分支>`；再次fetch，确认本地HEAD与远端分支SHA一致，等待该SHA的CI结果。

## 7. PR与双方进度核对

作者按[PR模板](.github/pull_request_template.md)填写行为变化、任务/需求、接口/迁移影响及真实验证。另一成员审查；有新提交、冲突解决或main更新时，重新验证和审批。

合并者必须核对：

1. A、B分别确认任务状态及相关本地未推送工作；远端没有提交不能证明本地没有依赖。
2. PR记录最新main、PR HEAD、相关A/B分支的远端SHA；无依赖写“无”，必需依赖未推送则禁止合并。
3. fetch后确认接口、迁移单head、共享组件和任务顺序一致；在最新main上的候选结果执行检查。
4. 检查结果属于当前候选SHA、另一人批准、讨论全部解决，再Squash merge；最终标题包含实际主提交者署名和中文说明。
5. 合并后两人拉取main，确认集成环境回归，再删除无后续依赖的已完成分支。

GitHub主线保护在P0配置：至少1名非作者审批、新提交撤销旧审批、分支最新、必要检查通过、讨论解决、禁止强推。CODEOWNERS只填写真实成员账号。CI最小读取权限，不用`pull_request_target`执行外来代码，不向普通PR提供生产或收费模型凭据。

## 8. 完成和发布

任务状态：Todo→In Progress→Review→Integrated→Done；受阻写明负责人和下一步。Done要求代码/契约/迁移/文档一致、验证通过、另一人审查、主线合入和集成回归。

发布按[质量验收](docs/07-quality-and-acceptance.md)与[运行手册](docs/08-deployment-and-operations.md)，标签、镜像、迁移、报告对应同一commit。范围、规则、栈或质量目标变更须双方评审并同步规范。推送、合并和发布分别执行，不把其中一步视为其他步骤的授权。
