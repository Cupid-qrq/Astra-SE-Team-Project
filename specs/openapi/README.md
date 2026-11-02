# 接口契约与交接

[总契约](../openapi.yaml)是B协调维护的当前OpenAPI 3.1入口，保留[A片段](a.openapi.json)的59个方法，另含B的两个健康方法。61个当前方法标记implemented，A契约内的方法均已注册；B其余业务路由随对应阶段接入。

客户端生成来源为总契约；A片段继续独立运行其原契约/验证应用检查。前端门禁验证总契约可解析、保留A DTO和生成类型一致。实际公共字段仍待A成员对本轮B候选确认，不能将工程测试代填双方冻结记录。

## 当前采用的公共约定

- Cookie为astra_session，HttpOnly/Secure/SameSite=Lax；写操作检验Origin及X-CSRF-Token。session及带X-Astra-Background: 1的GET不续空闲窗口。
- 角色STUDENT/TEACHER/ADMIN；账号/成员ACTIVE/DISABLED；课程ACTIVE/ARCHIVED；ai_policy沿用DISABLED/GUIDED及原业务收紧规则。
- JSON语法、重复键及无效UTF-8返回400；结构/字段422；体积413；身份401、权限403、不可见404、业务冲突409、个人限制429、平台暂不可用503。统一安全错误带请求ID/no-store，重试建议同时写Retry-After。
- profile资源字段沿用BR-07；语言版本、镜像digest和真实隔离证据在B2实测后确认。测试合成profile只用于装配验证。
- 教学API使用/api/v1前缀；/health/live和/health/ready位于服务根，后者以内部X-Readiness-Token认证。此令牌不提供给前端。

## 一致性与审查

`tools/check_api_contract.py`检查完整实际URL、方法、成功状态、operationId、参数、请求/响应schema、安全、components及服务器前缀。生产FastAPI从实际注册路由导出canonical元数据，生产59个教学方法同时校验请求和响应；行为另由真实PostgreSQL和正式应用浏览器验证。schema为契约驱动，未宣称Pydantic独立推导证明。

修改片段/总契约时核对同名paths/components，冲突人工评审；保留A字段的测试会拒绝漂移。运行生成命令并与API/页面一起审查，不手工改生成文件。UTF-8字节、总分100、唯一题目/语言、时间、归属和revision仍由服务端规则与事务保障。

A成员审批、双方未推送依赖和I0/I1待核对；详见[今日交接记录](../../docs/reports/2026-11-01-b-handoff.md)。预检执行、提交受理、成绩及模型等后续业务不能由当前契约/浏览器测试替代验收。

正式HTTP补充存储文本校验：text/varchar/JSONB及相关查询中的NUL返回422与安全字段位置；明确bytea测试/源码及散列密码字段保留原语义。内部审计/Outbox等未知约束故障属于503，业务Fault冲突仍409。

## 2026-11-02 固定帮助增量待 B 成员审查

已注册原五个维护方法（列表、创建、草稿读/写、发布），新增 `GET /feedback-catalogs/{id}/versions` 管理用版本摘要分页；草稿附加可选的范围、判定、语言、当前生效版及课程状态。旧 `FeedbackVersion` 公开投影和 attempt 冻结引用协议不变；A/B 两个契约同步生成客户端。正式列表/历史先 SQL 授权过滤，再签名游标分页。新增 FEEDBACK 审计类别使用现有表，无新迁移。

上述增量的代码与测试已备妥，B成员确认、双方本地未推送依赖和合并审批尚未代填，见[本批交接](../../docs/reports/2026-11-02-a-versioned-help.md)。
