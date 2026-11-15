# B前端动效补充

阶段ID：B-UI-MOTION-20261104。实施人B祝祎帆，成员评审人A覃锐谦；本次独立代码审查由代理review_motion_polish执行，不代填A审批。用户已明确授权继续美化、按阶段提交和推送，沿用已批准的前端主题。关联NFR-14/15/23及界面规范，业务FR规则不变。

用户要求继续参考鹰角粒子、视差和滚轮效果，范围为前端。已补查[招聘页](https://career.hypergryph.com/)内容分段与[来自星尘](https://exa.hypergryph.com/)的前后景及星点背景；终末地在当前访问中停留于资源加载，未作为已验证动效依据。沿用现有黑白/黄绿视觉。

## 文件与接口

- apps/web/src/components/ui/MotionEffects.tsx：共享动效偏好、暂停控件、粒子画布及页面滚动观察；不消费业务API。
- apps/web/src/components/ui/MotionEffects.test.tsx：暂停、偏好保存及系统减少动态回归。
- apps/web/src/app/App.tsx：挂载偏好和滚动观察，顶栏显示暂停按钮。
- apps/web/src/components/ui/Brand.tsx、apps/web/src/features/auth/LoginPage.tsx：在已有登录和轨道图形加入装饰画布。
- apps/web/src/styles/studio.css：粒子、层间视差、阅读位置与入场样式；暂停与减少动态覆盖。
- apps/web/e2e-integration/assignments.spec.ts：将旧主题文字色断言同步至已批准的新主题，保留业务与草稿恢复断言。
- docs/05-ui-specification.md、docs/project-status.md：同步视觉规则与本次实际检查。

提供本机localStorage键astra.visualMotion（on/off），根元素data-motion和只用于装饰的CSS变量。服务端身份、业务请求、API契约、数据库和模型配置均不涉及变更。

## 实施与验收

1. 暂停及减少动态先失败回归，再加入共享偏好。断言暂停立即生效、刷新保持、存储拒绝不阻止当前会话暂停、系统设置优先。
2. 登录背景呈现漂移点阵与指针近场连线；轨道和字标分层响应指针及原生滚动。画布持续绘制且指针移动改变图形变换。
3. 面板首次进入视口时短显现，顶部显示阅读位置。粒子在离开视口、页面隐藏及暂停/减少动态时停止。浏览器实际核验离屏暂停；页面隐藏分支经过代码审查，未单独声明真实后台标签页计时验收。
4. 保留原生滚动和控件命中区。编辑器子树不触发动效扫描，新增节点仅局部观察，窗口缩放更新阅读位置。

## 验证与收尾

Browser插件未提供，使用仓库已有Playwright Chromium。前端执行format:check、lint、typecheck、test、build；基础浏览器foundation/dialog在desktop/mobile运行。另在https://localhost:4176实际登录、移动指针、滚轮、暂停、刷新和切换减少动态，并查看桌面和390窄屏截图。具体结果见项目状态，原始输出位于本机忽略目录。

依赖为当前前端分支与服务中现有演示环境，无新增A业务接口或未推送依赖。审查两项Minor（整页扫描和窗口缩放）均已修正。尚未声称Firefox、Safari、真实移动设备或人工可用性验收。按既有授权提交推送，远端CI归属实际HEAD；未合入main前保持Review。回退使用git revert本阶段提交，再按原方式构建前端，不涉及数据回滚。
