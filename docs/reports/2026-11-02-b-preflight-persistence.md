# P1-B1a预检持久化验证记录

实施B祝祎帆，成员评审A覃锐谦。基线main 822687c9cdadf049d342f005fd9cef7f8abe53ff（PR#4已合入，主线CI run41403814285成功；API无审批记录，不代填成员批准），新分支feat/b/p1-preflight-persistence。用户明确选择延后评测VM，继续预检持久化。

## 范围与验证

- 纯冻结与事务预检端口沿用A内容/profile摘要和接口；16项纯边界先缺模块失败后通过。真实PG存储先缺端口失败；修正合成夹具字段名为A现有input_text/answer_text后，14项存储测试通过。新增3项策略锁故障用例先失败，移动至安全SQL错误边界后通过。
- b006建立run/cases/jobs，冻结私有bytea（含NUL）和不可变元数据；活跃内容去重、四类后段失败回滚、两连接竞争、数据库角色复核、跨课程/停用账号、陈旧与残缺证据、历史约束均有专用PG回归。
- 全B回归首轮231通过、1失败：旧健康检查固定b005，随迁移将严格head更新b006；对应就绪/错误head两项通过，未放宽检查。Ruff/format及B严格mypy通过。最终完整入口退出0：B232/A数据库114/前端58/契约6/浏览器59通过，12项既有跳过（.local/preflight-full-complete.log）。
- 既有B199后端基线、33项新增测试；A/前端/浏览器及离线模型检查全部保留。正式完整命令python tools/check_runtime.py；单项uv run --locked --project server pytest -c server/pyproject.toml server/tests/shared server/tests/judge。

## 边界与后续接线

此阶段只有独立持久化与事务查询产物，没有生产HTTP/Worker/物理执行；不能标FR-07或I0/I1完成。当前evidence读取只承认冻结绑定和精确全点AC的PASSED，生产没有完成写入接口；测试合成终态仅为结构/业务校验夹具。真实发布还依赖VM、监督端、Worker和端到端实测。

任务先global policy_guard再版本锁，锁内不做网络或执行；公开读取只投影元数据/点状态，原始私有材料不进入repr、异常链、审计/Outbox。版本引用RESTRICT，新公开预检接线前应与A适配有引用草稿的删除冲突；A已发布引用回指FK及执行槽位FK随对应实际接线设计补齐，不用伪造历史PASSED回填。jobs当前READY/DONE，租约、槽位和清理能力未交付。

oldali只读检查：Linux5.10/AlibabaCloudLinux3、KVM、2vCPU、内存约1.8GiB、系统盘约39GiB，控制器列为启用但未实测；无容器/隔离工具，存在本地监听服务，不能据此认定专用评测机。未改远端配置、安装或运行安全样例；资源不足完整四槽验收，用户选择后续再补。

本机继续使用既有Python3.12.13/uv0.13.5/PostgreSQL16.15独立_test库和随机schema；Build Web Apps的Postgres FK索引/锁设计检查适用，未切换托管数据库。临时日志/凭据在忽略.local，未提交隐藏材料或产物。回退不执行破坏性downgrade，不原位修改历史迁移。

## 完整检查中的定位与必要修复

首轮在A浏览器18项断言结束后收尾停滞，检查仅剩其Python测试服务、无浏览器或PG锁等待。核对本次完整PID祖先链后终止本轮验证树；该次明确未完成、不计通过。Browser插件不可用，按Frontend Testing Debugging使用仓库Playwright；后续生命周期复验可正常退出，未改超时或重试。

复跑实际发现建课缓存竞态：POST201(约136ms)，旧GET200(约177ms)，页面提示已创建却只有旧2条课程。初始列表仍进行时invalidateQueries沿用其promise，不发新请求。确定性InfiniteQueryObserver单元先失败；浏览器首版释放过早未复现，改为等创建成功提示后再释放旧响应，原实现稳定失败。CourseForms只增加取消旧查询并等待刷新，单元2/2和真实PG三视口3/3通过；迟到旧结果不能覆盖新数据。该修复独立中文fix提交，实际贡献人B，后续A成员审查，未改API或样式。

复现trace存放忽略.local/preflight-race-evidence，根日志首轮preflight-full.log、复跑preflight-full-final.log；最终候选完整入口日志preflight-full-complete.log。本轮根入口检查将新增浏览器用例分别跑在A与正式B host，覆盖三个视口；不把功能回归当性能验收。取消语义参考[TanStack官方说明](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation)。
