# 业务服务与Worker

B建立公共工程，A/B按[架构模块表](../docs/02-architecture.md)实现各自业务。P0建立pyproject、uv锁文件、FastAPI、SQLAlchemy、Alembic、pytest、格式与类型检查。

```text
app/api/                 路由装配与统一协议
app/modules/             identity、courses、problems等业务模块
app/shared/              事务、时钟、ID、错误与公共端口
app/adapters/            Judge0、模型和外部基础设施适配
app/workers/             评测、提示、通知、恢复与维护进程
migrations/              Alembic迁移（B协调单head）
tests/unit/              领域与应用用例
tests/integration/       真实PostgreSQL与适配器集成
```

所有进程共用规则实现；Worker不能绕过授权和事务直接修改成绩。A 已在 `app/modules` 实现身份/课程、题目、作业和固定帮助基础；独立 API、PostgreSQL 迁移和检查方法见 [A线接入说明](a_line/README.md)。B 负责的正式总入口、shared 层、Worker 和总迁移仍待集成；独立验证入口不作为生产入口。
