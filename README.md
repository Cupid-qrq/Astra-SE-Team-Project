# Astra · 课程编程学习平台

Astra 为课程教学提供作业管理、代码评测、成绩管理和学习反馈。支持学生、任课教师、管理员三类角色，以及 C++17、Python 3 单文件程序。

正式仓库：[Cupid-qrq/Astra-SE-Team-Project](https://github.com/Cupid-qrq/Astra-SE-Team-Project)。当前为已审定的开发规划基线v0.3，后续按P0—P3推进；业务代码尚未实现。

## 开发文档

| 文档 | 内容 |
| --- | --- |
| [开发总纲](docs/00-development-plan.md) | 产品目标、范围、技术路线、职责与交付原则 |
| [需求规格](docs/01-requirements.md) | 角色、功能、业务规则与质量要求 |
| [架构设计](docs/02-architecture.md) | 模块边界、运行流程、并发与一致性 |
| [接口契约](docs/03-api-contract.md) | HTTP API、请求响应、权限及错误约定 |
| [数据设计](docs/04-data-design.md) | 实体、字段、约束、索引与事务 |
| [界面规范](docs/05-ui-specification.md) | 视觉语言、页面结构、交互与可访问性 |
| [分工与阶段计划](docs/06-roadmap.md) | A/B 路线、P0—P3 任务、依赖及交付门槛 |
| [质量与验收](docs/07-quality-and-acceptance.md) | 测试矩阵、负载、质量门槛与验收流程 |
| [部署与运维](docs/08-deployment-and-operations.md) | 环境、配置、发布、恢复与数据留存 |
| [开发工作流](CONTRIBUTING.md) | Superpowers/Build Web Apps、任务、中文提交、审查、同步及推送检查 |
| [当前项目状态](docs/project-status.md) | 基线、阶段进度、待落实事项和验证边界 |

## 仓库结构

```text
.github/           PR 模板、任务模板、持续集成
apps/web/          React 前端
server/            FastAPI 业务服务、Worker、适配器、迁移
specs/             跨端契约与需求追踪
tests/             跨服务、浏览器、容量和安全测试
infra/             部署配置、运行手册配套脚本
tools/             仓库检查、推送预检及工具回归测试
docs/              当前开发规范
archive/           两份选定提交的只读原件
```

功能实现从 P0 的环境和纵向联调开始。各目录目前包含职责说明；不能据目录存在判断模块已完成。原提交材料只用于追溯，开发按当前文档执行。

## 本地文档检查

在仓库根目录使用 Python 3.11 或以上版本运行：

```powershell
python tools/check_repository.py
python -m unittest discover -s tools/tests -v
git diff --check
```

业务构建、测试和部署命令由 P0 建立并接入质量门槛；现阶段文档检查不代表软件功能通过验收。
