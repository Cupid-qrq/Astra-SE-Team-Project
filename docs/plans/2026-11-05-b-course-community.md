# B课程榜单与题目讨论实施契约

负责人B祝祎帆；成员评审A覃锐谦待核验，实施后独立代理审查。用户2026-11-05要求课程排行、题目讨论，明确两个榜单都要。本次授权包含必要的持久化、接口及前端。新增FR-30课程榜单与FR-31讨论（待在主需求表同步）。使用现有会话/CSRF/事务/课程授权，管理员不自动取得课程讨论访问。

## 规则

仅本课在课且账号ACTIVE学生和任课教师访问。归档只读，已清理拒绝。练习进度榜实际统计已开放且已发布作业中的当前有效FORMAL AC，按(作业,题目)去重，不计练习、旧轮次及SE，不暴露隐藏测试；名称明确“正式作业通过题数”。成绩榜累计当前有效的已发布成绩版本，epoch不匹配、重评中或公平复核待裁决的作业不纳入，并返回计入作业数。同分并列，不按速度打破平局，按稳定entry_id排序分页。默认匿名，学生按课程设置是否显示姓名，教师可识别学生；其他学生响应不得含student_id。本人is_me=true。允许真实0分，不编造热度和学生。

讨论按course_id/problem_id/version_id隔离。学生必须通过已开放/已发布作业或已授权练习能够阅读该题版本；教师依题目所属课程授权。不能提前通过讨论泄露未开放题。主题/回复正文纯文本或现有SafeMarkdown，禁止自动加载外链图片/HTML。标题1-120，正文1-4000，空白拒绝。每用户发帖/回复至少10秒间隔、每课程小时最多30条。教师可置顶、锁定、隐藏；作者可标记解决与隐藏自己的内容。隐藏正文对普通读者不返回，数据库保留供治理。课程归档不可发帖或管理。写入记录审计，作者/时间由服务端产生。

## 固定跨端接口（新增，不修改既有）

GET /courses/{id}/leaderboard?kind=progress|grades&cursor&limit -> {course_id,kind,updated_at,included_assignments,show_name,items:[{entry_id,rank,display_name,value,is_me}],next_cursor}
PATCH /courses/{id}/leaderboard-preference {show_name:boolean} -> {show_name:boolean}；只允许学生设置本人。
GET /courses/{id}/problems/{problem_id}/discussions?version_id=UUID&cursor&limit -> {items:Thread[],next_cursor}
POST 同路径 {version_id,title,body} -> Thread (201)
GET /discussions/{id}?cursor&limit -> {thread:Thread,replies:Reply[],next_cursor}
POST /discussions/{id}/replies {body} -> Reply (201)
PATCH /discussions/{id} {expected_revision, resolved?, locked?, pinned?, hidden?, reason:10-500} -> Thread；未知字段拒绝、至少一个状态字段。
PATCH /discussion-replies/{id} {expected_revision,hidden:boolean,reason:10-500} -> Reply

Thread={thread_id,course_id,problem_id,version_id,title,body,author_name,is_mine,can_moderate,resolved,locked,pinned,hidden,revision,reply_count,created_at,updated_at}
Reply={reply_id,thread_id,body,author_name,is_mine,hidden,revision,created_at}
隐藏返回body为空，thread标题为“已隐藏的讨论”，教师可查看原内容以管理，作者隐藏后普通读取也不返回正文。详情列表以现有签名游标处理，服务方法返回原始items，由API接线负责c['page']或pager分页，主题按置顶优先、发布时间倒序及UUID稳定排序；回复按发布时间正序及UUID排序，签名游标保持该顺序。

## 文件与方法分工

排行榜实施：server/app/modules/community/leaderboards.py，类Leaderboards(repo,effects)，read(actor,course_id,kind)->非分页响应，preference(actor,course_id,body)。自有metadata注册文件leaderboard_models.py，迁移b018（down b017）仅榜单偏好。tests/judge/test_leaderboards.py。不要改shared/metadata.py，由根代理统一导入。
讨论实施：server/app/modules/community/discussions.py，类Discussions(repo,effects)，list(actor,course_id,problem_id,version_id)->list Thread，create(actor,course_id,problem_id,body)->Thread，read(actor,id)->{thread,replies}，reply(actor,id,body)->Reply，update(actor,id,body)->Thread，update_reply(actor,id,body)->Reply。discussion_models.py；迁移b019（down b018）两表。tests/judge/test_discussions.py。不要改shared/metadata.py，由根代理统一导入。
前端实施：apps/web/src/features/community/*，communityApi.ts手写封装通过现有传输/CSRF可复用client.ts公开request方法或由根代理补transport；只修改新增文件、CoursePage/EditorPage/AssignmentPages/PracticePolicy的入口和studio.css。榜单路由/course/:id需按项目使用/courses/:id/leaderboard；讨论列表/courses/:id/problems/:problemId/discussions?version_id=…，详情/discussions/:id。根代理维护App路由、API契约/服务注册、规范与集成。

## 验证与发布

真实PostgreSQL权限/同分去重/迟到轮次/重评与匿名投影、讨论跨课/版本/隐藏/锁定/限流/归档测试；HTTP授权及CSRF；生成契约/客户端；前端交互和桌面/窄屏。迁移前本机专用库备份；不修改既有历史。阶段完成分别提交，按既有授权推送B分支，合并与外部验收另记。无真实模型调用。回退应用可忽略新增表；已产生讨论不得直接drop，保留数据或使用兼容备份恢复。

用户追加：课程列表每项和详情标题下显示完整课程编号及复制按钮，支持按编号搜索。各页说明移至顶栏“操作与功能说明”，默认折叠，展开分为功能介绍和操作步骤。CopyIdentifier复制拒绝时保留完整文本供手动复制。
