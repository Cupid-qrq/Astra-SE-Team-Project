# 跨端契约

[traceability.json](traceability.json)登记FR/NFR负责人、阶段、模块、实施任务及验收编号；FR另映射主要API和数据表。`tasks`记录任务负责人、工作量和显式依赖，阶段间依赖由P0—P3门槛约束。NFR的`implementation_phase`表示首次落地，`phase`表示最终回归阶段。

P0按[接口契约](../docs/03-api-contract.md)建立OpenAPI 3.1、生成客户端和Mock。先合并契约再并行实现。数据库运行结构以Alembic迁移为准；变更同时更新数据规范。未有实现与测试报告前状态保持planned，verified必须引用真实证据。
