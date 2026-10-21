# 部署配置

负责人B，按课程规模提供脚本与配置，不建设独立运维平台。P0建立业务区Compose、代理与HTTPS示例、环境变量模板和健康检查；评测区配置独立管理，不能用一个Compose网络代替虚拟机隔离。

```text
compose/                 本地/集成业务服务编排
proxy/                   同源路由和HTTPS配置
judge/                   独立VM执行器profile与监督配置
backup/                  备份、恢复及校验脚本
monitoring/              健康探针及脱敏日志配置（不部署独立监控平台）
```

具体配置遵循[部署与运维](../docs/08-deployment-and-operations.md)。凭据、数据库卷、备份正文和测试产物不提交Git。当前无已部署环境。
