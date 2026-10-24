# Web 前端

A维护公共组件和教学/学习页面；B完整负责提交结果/历史、成绩/重评、admin及通知页面与测试。公共路由、令牌和生成客户端变更需协调，不把B的页面交由A代做。P0由A建立React/TypeScript/Vite工程、pnpm锁文件、类型检查、Vitest、Playwright和生产构建。

```text
src/app/                 路由、会话和应用壳
src/features/            按业务模块组织页面、查询和状态
src/components/ui/       统一基础组件
src/lib/api/             从OpenAPI生成的客户端与适配
src/styles/              设计令牌、字体和全局样式
```

API真值与服务端一致，不在前端计算正式资格或最终成绩。遵循[界面规范](../../docs/05-ui-specification.md)与[接口契约](../../docs/03-api-contract.md)。当前交付 P0 公共基础与 Mock 联调示例；真实身份、课程写入、评测和成绩属于后续业务实现。

## 启动和检查

使用 Node 24.16.0、pnpm 11.21.0，在仓库根目录运行：

```powershell
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web exec playwright install chromium
python -m pip install -r tools/requirements-model.txt
pnpm --dir apps/web dev:mock
```

访问终端输出的本机地址。演示账号 `demo_student`，密码 `ExamplePass123`；均为公开虚构数据。`demo_teacher` 展示教师身份；`demo_empty`、`demo_expired`、`demo_unavailable` 分别用于空列表、进入详情后会话失效、一次503后主动重试。所有演示账号使用同一虚构密码，不得用于真实部署。刷新保留的仅为该标签页的演示账号名，退出后清除。

`pnpm --dir apps/web dev` 默认走真实 API，代理目标默认 `http://127.0.0.1:8000`，可通过启动进程的 `VITE_API_PROXY_TARGET` 环境变量覆盖。生产由反向代理将 `/api/v1` 转发到同源后端；不得向浏览器提供数据库或模型凭据。生产构建即使指定 mock mode 也不会包含 Mock；`production:check` 检查 worker/演示凭据未打包。

```powershell
python tools/check_runtime.py
```

唯一入口调用 `tools/check_all.ps1` → 独立进程 `tools/check_web.ps1`，依次执行冻结安装、lint、类型、契约生成一致性、单元、生产构建、生产 Mock 排除、Playwright 三视口冒烟，再执行模型离线 schema 核验。任一步失败返回非零。CI执行同一入口，浏览器/工具依赖在CI准备步骤安装。

修改 A 契约后运行 `pnpm --dir apps/web contracts:generate`，将生成类型与契约一起评审；手工编辑生成类型会被 `contracts:check` 拒绝。公共组件使用系统字体回退，不向第三方字体服务发送请求。

## 可复用组件

`Button` 支持 primary/secondary/quiet/danger 与 busy；`Field` 关联 label/帮助/错误；`DataTable<T>` 使用列 render、稳定 rowKey、表头与空态；`StatePanel` 覆盖加载/空/错误/无权限；`ConfirmDialog` 提供取消初始焦点、Tab边界、Escape和焦点恢复。样式仅消费 `src/styles/tokens.css`。

当前路由：登录、我的课程、课程作业摘要和404。其他业务页面按原分工在P1—P3交付，不建立可点击但无实现的业务按钮。

## 与 B 线接线

1. 合并前核对 [A 契约交接](../../specs/openapi/README.md) 中的公共字段提案；B 维护总契约/服务层，A 重生成客户端。
2. B 的真实服务提供会话、登录、退出、课程及课程作业 GET；使用独立测试库和虚构账号。先确认 Cookie/CSRF/Origin/统一错误与响应字段。
3. `dev` 模式启动前端，实际操作登录→课程→详情→退出；在 PostgreSQL 核查账号/课程读取来源及会话创建/撤销。保留当前 SHA 和真实输出。
4. 将B真实数据库/迁移检查追加至 `tools/check_all.ps1`；当前A分支调度器不能覆盖B版本。全路由及FastAPI语义差异、真实CI、两人干净检出和I0另行验收。

Playwright 在本阶段使用 Chromium，覆盖1366×768、1440×900、390×844。Browser插件未提供，因此按Frontend Testing Debugging流程使用项目Playwright；测试截图/trace位于忽略的test-results。跨浏览器最终验收仍属P3。
