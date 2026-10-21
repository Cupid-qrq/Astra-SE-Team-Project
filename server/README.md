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

所有进程共用规则实现；Worker不能绕过授权和事务直接修改成绩。当前只包含目录约定，尚未提供API和迁移。
