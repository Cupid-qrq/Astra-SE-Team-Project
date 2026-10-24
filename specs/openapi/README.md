# A 模块契约交接

`a.openapi.json` 是 OpenAPI 3.1 A 线片段，覆盖接口规范中54个方法，非运行服务导出；B预检、提交、成绩、管理运维、通知路由仍由B维护。公共schema目前是A提案，不代表双方已冻结。

契约通过OpenAPI解析、文档路由覆盖、权限/错误/CSRF声明、严格字段投影检查；从此文件生成`apps/web/src/lib/api/schema.d.ts`，生成差异进入门禁。MSW仅实现登录/退出/会话/课程/课程作业，其余API返回明确503 `MOCK_NOT_IMPLEMENTED`。

## 待双方确定的公共细节

- 会话Cookie暂名`astra_session`，服务端必须设置HttpOnly/Secure/SameSite=Lax；Origin由浏览器自动发送，服务端对全部写操作校验；CSRF头为`X-CSRF-Token`。
- 角色为STUDENT/TEACHER/ADMIN，账号/成员状态ACTIVE/DISABLED，课程ACTIVE/ARCHIVED；与B公共身份投影核对。
- `ai_policy`采用DISABLED/GUIDED的字段提案；不得据此修改开放后只可收紧及同族授权规则。
- profile中的语言版本、镜像digest由B2实测冻结；资源值来自BR-07，不将schema常量视为隔离证明。
- 草稿source_ref、列表title、分页及帮助/模板版本号的精确DTO在服务落地时核对，破坏性修改须同步生成代码与测试。
- OpenAPI表达码点/结构边界，UTF-8字节、作业20题总分100、唯一题目/语言、时间先后、对象归属和并发revision仍须服务端事务校验。

## 合并程序

由B维护总入口`specs/openapi.yaml`与公共schema；A/B先逐项确认以上字段，再合并paths/components，相同方法或schema名冲突必须人工确认，不能last-write-wins。A将生成脚本输入切换到总契约并重生成。由B导出当前FastAPI OpenAPI；比较每个方法的参数、请求/响应schema、必需字段、枚举、状态码和安全要求，消除差异后纳入唯一入口。当前没有B片段和FastAPI导出，因此不生成看似完整的总契约。

权限与错误示例集中在每个操作的`x-roles`及共享responses中：401未登录、403无权、404不可见、409版本冲突、413字节超限、422输入错误、429个人限制、503平台不可用。真实授权测试仍在P1实施；客户端隐藏入口不能代替服务端校验。
