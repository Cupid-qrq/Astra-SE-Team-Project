# 跨模块测试

```text
contract/                HTTP与内部端口契约、安全投影
system/                  ST-01—ST-17及故障恢复
e2e/                     三角色真实浏览器流程
performance/             W-01—W-04及容量边界
security/                隔离、权限、内容安全与提示攻击样例
fixtures/                虚构账号、自编题目和可重现程序
```

模块单元/数据库集成测试分别放在前端和server工程；此目录放跨模块验证。由[质量与验收](../docs/07-quality-and-acceptance.md)定义范围。真实执行器安全样例只在专用隔离环境运行，模型收费测试不进入普通无条件CI。当前尚未实现这些测试。
