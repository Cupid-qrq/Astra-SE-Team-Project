# P0-B1 / P0-B2 环境核验记录

日期：2026-10-24（北京时间）。记录人：B 线执行代理；成员评审人：A覃锐谦；用户已确认 A 尚未审阅，本轮仅完成准备与核验。

本记录只证明下表中的读取和工具核验已执行，不证明业务、数据库集成或执行隔离通过。

## 1. 版本和工作区

| 项目 | 观测结果 |
| --- | --- |
| 本地开发基线 | `cd4edf7fd999402e8aff7a1a83618b516f6f9cda` |
| 正式仓库 main | `git ls-remote origin refs/heads/main` 返回相同 SHA；未改写远端 |
| 实施分支 | `feat/b/p0-foundation-isolation` |
| 隔离工作区 | Codex 管理的 `b-p0-foundation-isolation/Astra-SE-Team-Project`；从 main 建立，不复制原目录未提交内容 |
| 原目录 | 已有暂存实验材料、核查附件和未跟踪 `fankui.txt`；未修改或暂存这些内容 |

## 2. 实际环境探测

| 检查 | 结果 | 对本任务的含义 |
| --- | --- | --- |
| Windows Python | `python --version`：3.13.5（Anaconda） | 不直接沿用其全局包；工程拟使用独立 3.12 环境 |
| uv | `uv --version`：0.10.10 | 已可调用；沙箱外核验可读取安装清单 |
| Python 3.12 | `uv python list --only-installed`：本机已有 CPython 3.12.13 | 底座无需先另装解释器；依赖与锁文件尚未建立 |
| PowerShell | `Get-Command pwsh`：Codex bundled PowerShell | 可用于统一入口；尚未建立产品检查脚本 |
| WSL | `wsl --list --verbose`：Ubuntu，WSL2 | 现有开发环境可复用；不能据此认定有独立评测区 |
| WSL 系统 | Ubuntu 24.04.4 LTS；Linux 6.6.87.2-microsoft-standard-WSL2 | 仅环境指纹 |
| WSL Python/编译器 | Python 3.12.3；gcc/g++ 13.3.0 | 只读取版本，未编译或运行评测样例 |
| WSL Docker | CLI 和 `/var/run/docker.sock` 均未发现 | 尚不能执行 Compose 启动和真实数据库服务检查 |
| WSL PostgreSQL | 未发现 psql 或 `/usr/lib/postgresql` | 尚无已核验可用测试数据库 |
| Windows Docker/PostgreSQL | PATH 及已检查的常规安装位置未发现 | 不能声称机器已有可用服务；也不据此证明所有磁盘均不存在安装 |
| WSL 资源 | `free -m`：总内存 15844 MiB；`nproc`：24；`df -h /`：可用约 952 GiB | 观测值不是双 VM 资源分配或正式容量验收 |
| 专用评测 VM | 本次尚无已登记、可核验的实例/管理入口/profile | V-01—V-06 均未执行 |

探测命令仅包含版本、程序可用性、系统/内存/磁盘摘要；未读取密钥、会话、学生代码、隐藏测试或数据库正文。

## 3. 插件核验

- Superpowers：插件目录搜索可找到；依赖检查返回已安装、已启用，但本会话未提供可调用的相关技能，已检查的本地技能缓存也未找到对应 SKILL.md。版本与实际能力使用尚无法确认，不能写已使用。
- Build Web Apps：本会话无相关技能；插件搜索未取得可确认的同名结果。不将 Sites、Replit 等其他产品当作该插件替代。
- 已使用插件管理能力查找安装/可用状态；这不能替代双方实际加载核验。

## 4. 执行器能力核对

核对[Judge0 CE 官方 API 文档](https://ce.judge0.com/)：文档声明对应 v1.13.1，删除 submission 对排队/运行状态返回 400。该 HTTP 删除接口不足以实现项目要求的“取消、物理退出与清理证明”。这是文档能力核对，不是本项目实际部署结果；部署版本、监督清理和各资源限制仍须实测。

实施范围、失败断言与待确认交接见[实施计划](../plans/2026-10-24-p0-b-foundation-and-isolation.md)。P0-A1 和成员计划审查未完成前，保留准备结果，不将任务标为已实施或完成。

## 5. 本轮准备验证

执行位置为上述独立工作区；基线 SHA 加本轮未提交的准备文档，尚无新 commit，不将这些结果归属到某个已发布版本。

| 命令/检查 | 实际结果 | 边界 |
| --- | --- | --- |
| `python -B tools/check_repository.py` | 841 项，错误 0，退出 0 | 文档/追踪/链接/归档完整性 |
| `python -B -m unittest discover -s tools/tests -v` | 12 项通过，退出 0 | 既有仓库门禁脚本回归 |
| `git diff --check -- . ':(exclude)archive/submissions/**'` | 退出 0 | 已跟踪修改的空白检查 |
| 新增文档 UTF-8/尾随空白检查 | 2 份文档均无尾随空白，退出 0 | 额外覆盖未跟踪新文件 |
| `python -B tools/check_runtime.py` | 纯规划检出，无产品运行检查适用 | 不能解读为数据库/业务检查通过 |

未执行：工程构建、依赖同步、真实数据库迁移/集成、容器启动、Judge0 适配测试、V-01—V-06。原因是文件级计划尚待成员审查、工程尚未实施，且未有已核验的数据库与专用执行环境。

供 A 审查的计划文件 SHA-256：`5599ba8e48fc24b7d033e3c0e9d2c8669a184dd47667ea75df83e3e1c2a2706e`。内容变化后应重新核对审查范围。最终复核同时覆盖计划、报告和项目状态三份文档的 UTF-8 与尾随空白，结果无错误。
