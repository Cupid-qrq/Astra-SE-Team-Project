# 模型配置与验证

当前适用v0.4。用户于2026-11-03提供deepseek-flash、官方接口、用户环境变量DeepSeek_API及本轮20元预算。`runtime.example.json`是本轮运行配置，默认关闭；旧`config.example.json`及其schema仍是P0离线检查夹具。以下早期说明保留其日期语境，不能当作当前配置。验证见[本批报告](../../docs/reports/2026-11-03-a-live-model.md)。

## 本轮独立模型回归

在仓库根目录用server虚拟环境运行，默认只冻结合成样例而不联网：

```powershell
& server/.venv/Scripts/python.exe tools/model_live.py
```

真实调用需将`runtime.example.json`复制到忽略的`.local/model-live/runtime.json`，核对参数并将enabled设为true。密钥留在`DeepSeek_API`环境变量；Windows可从用户变量读取，无需复制到配置文件。Linux部署需显式注入进程环境变量。模板采用本目录`quality-template.json`，30例来自自编`quality-cases.json`。

```powershell
& server/.venv/Scripts/python.exe tools/model_live.py --profile .local/model-live/runtime.json --live --limit 1
```

`--limit`控制本次最多新增多少个首轮请求；再次运行只处理尚未预占的案例，不自动重试失败/中断案例。完整账本固定保存在`.local/model-live/budget.sqlite3`，不能通过删除/另开工作树重置授权总预算。结果在对应清单摘要目录。评分用的预期原因和范围不会发送给供应商。review-a/b.template.json留空，需真实评审独立填写，代理检查不冒充成员评分。

该工具是合成适配器回归，不经过学生账号和正式提交；即使30例结构有效，也不代表每日20次额度、正式W-03或端到端验收通过。正常业务的限额测试仍在真实PG用例中，完整验收等B来源接线后按正常账号/日期执行。

评分模板只在30例均有已保存终态时生成，避免运行中的请求被提前算成失败。确认调用进程已经停止后，可用同一profile加`--finalize-interrupted ATTEMPT_ID`显式将遗留请求记为失败；未知费用全额保留且不再重发。该操作不能与`--live`组合，不得用于仍在运行的请求。已填写的评分文件始终保留。

## 课程提示 Worker

HTTP进程设置`ASTRA_MODEL_PROFILE_FILE`指向核验后的配置，同一配置用于独立Worker。配置加载不读取密钥、不自动建表、不启动付费后台任务。B须提供受信`Sources`工厂；缺失时服务继续关闭。完成迁移后，在server目录显式初始化不可变模型配置及收紧后的预算：

```powershell
python -m app.modules.learning.hint_worker --profile ../.local/model-runtime.json --bootstrap
# B工厂是后续接入模块，以下占位名称不能直接执行：
python -m app.modules.learning.hint_worker --profile ../.local/model-runtime.json --sources B_MODULE:factory --once
```

不带`--once`时独立Worker轮询；没有任务时等待0.5秒，外发不持有数据库事务。HTTP必须注入同一受信来源并共享配置ID。冻结模板的启用与发布分开，不能用最新草稿代替已验版本。先在模板页面保存并发布，再由部署操作明确选定目录ID、版本ID、页面返回的SHA-256、现有管理员或本课教师ID及理由：

```powershell
python -m app.modules.learning.hint_worker --profile ../.local/model-runtime.json --activate-template TEMPLATE_ID --version VERSION_ID --checksum SHA256 --actor USER_ID --reason "明确说明已核验版本及本次启用理由"
```

该受信部署命令重验账号、归属、归档、版本和校验值，启用指针、TEMPLATE_ACTIVATED审计及Outbox同事务；不会自动追随之后发布的新版本。回退也显式选择已核验的历史版本，已有提示保留原引用。内容门禁只识别明显代码/危险输出，不能代替语义质量评审。

**预算不能重复分配。** 本轮20元包含工具回归和后续Worker调用。工具和课程数据库账本相互独立；启用Worker前必须扣除本地账本已占用金额，并把剩余额度写入部署配置。未知供应商费用继续全额预占，usage乘高峰价只记估算；实际账单取得后才调用`HintService.reconcile`结算。不要把默认规划500元当作本轮授权。

## 早期离线准备记录

发起人于2026-10-24确认：账号和API Key暂未准备，本次仅完成schema、配置和离线测试。该次离线准备没有网络调用，不读取密钥。

`input.schema.json`只允许公开题目/样例、本人代码、语言、脱敏诊断、粗粒度判定和附加问题。`output.schema.json`限定错误类别、定位线索、检查方向、学习建议四段。脚本额外检查输入24KiB、样例每份4KiB、输出2000码点/8KiB；拒绝额外字段、错误类型和重复JSON键。

```powershell
python -m pip install -r tools/requirements-model.txt
python tools/model_probe.py
python -m unittest discover -s tools/tests -p test_model_probe.py -v
```

输出只含输入摘要与离线标记，不输出源码；`actual_cost_cny=null`表示没有真实计费记录，不将未知费用记0。示例代码为项目自编，无真实学生信息。schema校验不能证明字段来源可信、授权有效或正文安全；完整提示安全、配额/双预算、事务预占和真实质量验证仍由P2完成。

## 官方资料核对（2026-10-24）

- [模型和价格](https://api-docs.deepseek.com/quick_start/pricing/)当日列出`deepseek-flash`，对应展示版本DeepSeek-V4.1-Flash-1017；该别名不是不可变版本。英文页面美元计价，峰时未命中输入0.30美元/百万token、输出1.20美元/百万token；谷时分别0.15/0.60。此处仅为资料快照，不作为人民币预算结算配置。
- [JSON Output](https://api-docs.deepseek.com/guides/json_mode/)要求`response_format=json_object`及包含json要求的提示，仍需本地校验空内容、截断和schema；不能仅以供应商JSON模式认定有效。
- [使用条款](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html)页面更新日为2026-03-27，涉及输入/输出使用及产品改进用途；专门条款可能优先。隐私政策页面本次读取超时，账号地区、实际适用条款、API数据留存和训练退出机制尚未核实，不能声称已满足数据条款门槛。

启用前由账号持有人确认实际区域、人民币价格/计费币种及转换依据、数据条款和预算。配置保留每日20元/项目500元的规划上限，模型、token上限、价格和核验引用为空且enabled=false。后续需另行实现经审查的真实ModelPort与一次自编样例连通，不通过修改该离线模板的开关启用收费服务。

## A 线提示运行组件

应用中的 hint_service、hint_store、policy_rules 和 hint_runner 提供持久接纳、权限重验、预算结算和独立 Worker 单轮执行。DeepSeekTransport 显式接收冻结模型、价格与模板、token 计数器和传输层。启动配置默认关闭，部署接线见 server/README.md。

质量核算入口为 python tools/model_quality.py manifest.json review-a.json review-b.json。manifest 由 tools.model_quality.freeze 冻结30例输入摘要、预期原因、允许范围、模型与模板版本。两位成员分别记录相同首次请求的 D/A/S 布尔评分和终态，分歧按0计。工具校验分布、唯一案例/请求及摘要，输出方向、可执行性、安全数量和通过状态。人工评分的真实性与额外20例注入/20例页面安全证据另行审阅。
