# B执行适配与独立VM准备验证记录

实施B祝祎帆，成员评审A覃锐谦。范围从7c95201开始，基于main ec3fb0bd8449700dfd4a9e69d1910d31d0f268e1；用户转达A已确认上一批交接，授权本批连续阶段提交和检查后推送B功能分支。新实现仍需A成员审查，不代填GitHub审批。

## 阶段

| 阶段 | 交付 | 验证/提交 |
| --- | --- | --- |
| S4a | 租约/摘要/执行端口、A profile_digest绑定与部署语言ID允许列表 | RED→GREEN 23项；完整入口0，B98；dae786c |
| S4b | 固定HTTPS Judge0、未知创建/原字节/指标/状态映射及监督清理候选协议 | RED→GREEN 85项；完整入口0，B160；f26bee2 |
| S5-prep | VM登记、证据指纹与文件摘要、显式GET预检、默认拒绝模板 | 114项评测相关测试通过；最终完整入口0（B189），其余A数据库114/前端57/契约6/浏览器53通过，12项既有跳过；日志.local/s5-prep-complete.log |

完整入口为python tools/check_runtime.py，内部运行统一tools/check_all.ps1，保留前端、A数据库/浏览器、离线模型和B检查。前两阶段均A数据库114、前端57、契约6、浏览器53通过，另12项既有跳过不计通过；A领域分支覆盖98.25%，不代表B或全应用覆盖率。仓库静态和19项工具回归另行通过，不称业务验收。

本机使用既有B worktree、Python3.12.13/uv0.13.5、Node24.16/pnpm11.21、专用非超级用户PostgreSQL16.15测试库；随机schema用于真实集成回归。数据库连接与日志只在忽略.local，未提交凭据、真实隐藏材料或临时产物。

## 失败与复验

- 先观察缺模块失败，再实现端口/配置、HTTP适配、登记库。补充布尔租约、底层HTTP环境继承、持续滴流、非有限JSON、目标别名、目录访问失败及UNC/符号链接解析前拒绝等实际RED→GREEN边界；当前严格类型/格式通过。
- pytest默认临时目录ACL拒绝访问，使用既有工程模式在忽略目录创建独占临时目录；清理前核对解析路径在本工作区内，不修改系统目录权限。
- S4a初轮在自动移除导入后留下首行空白，格式化后完整重跑0；未放宽规则。
- S5-prep首轮A浏览器3项5秒提示/列表断言失败，trace显示保存201及后续读取等待。A/web实现与f26bee2完全一致；原设置单独复验题目/成员三个视口6项全部通过，32.4秒；未加重试/延时、改超时或删用例。失败trace留在忽略.local/s5-failed-A-traces，完整复跑结果见阶段记录。不能把这次复验当性能验收。

## 边界与交接

- 不在业务机运行、编译学生代码或隔离探针；所有执行HTTP测试均MockTransport。未部署VM/执行器/监督端，未联网探测真实管理入口，未执行V-01—V-06；当前WSL只供数据库回归。
- 专用Linux评测VM来自已审定部署/质量规范和P0-B2，规范未指定A采购，也不要求云付费。资源目标及登记操作见[运行准备](../../infra/judge/README.md)。
- 新监督协议是候选：创建前持久登记完整身份、迟到创建fence、未知创建收敛及物理停止/目录清理证明须由VM受信接入层实现。原生Judge0 DELETE不代表终止；本批HTTP证明校验不能证明物理真实性。
- 本批没有生产Worker、持久创建账本、队列/槽位、整轮截止、正式预检/成绩业务接入。登记检查成功也只表示记录齐全待成员复核，execution_enabled始终false；缺VM/监督实现/实测时不得开启正式执行。
- 端口消费A既有profile摘要，不改A接口、历史迁移或归档；成员交叉复核新候选协议后，再安排独立VM上的真实隔离实测及冻结。代理独立审查结果由本批收尾回执给出，不替代A成员审批、主线合入和集成验收。

## 复现入口

```powershell
uv run --locked --project server pytest -c server/pyproject.toml server/tests/judge
uv run --locked --project server python tools/verify_judge.py --registration infra/judge/deployment.example.json
python tools/check_runtime.py
```

第二条应返回UNVERIFIED、execution_enabled=false、退出2；需要实际登记与秘密环境变量后才可显式--probe读取管理配置。准备配置不会自动连接或执行代码。
