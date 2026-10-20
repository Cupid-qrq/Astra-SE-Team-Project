# Web 前端

A维护公共组件和教学/学习页面；B完整负责提交结果/历史、成绩/重评、admin及通知页面与测试。公共路由、令牌和生成客户端变更需协调，不把B的页面交由A代做。P0由A建立React/TypeScript/Vite工程、pnpm锁文件、类型检查、Vitest、Playwright和生产构建。

```text
src/app/                 路由、会话和应用壳
src/features/            按业务模块组织页面、查询和状态
src/components/ui/       统一基础组件
src/lib/api/             从OpenAPI生成的客户端与适配
src/styles/              设计令牌、字体和全局样式
```

API真值与服务端一致，不在前端计算正式资格或最终成绩。遵循[界面规范](../../docs/05-ui-specification.md)与[接口契约](../../docs/03-api-contract.md)。当前没有业务实现或可运行构建命令。
