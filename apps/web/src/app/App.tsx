import { BrandMark } from '../components/ui/Brand'
import { ButtonHints } from '../components/ui/ButtonHints'
import { RetentionPage } from '../features/operations/RetentionPage'
import { ControlsPage } from '../features/operations/ControlsPage'
import { AdminPage } from '../features/operations/AdminPage'
import { TeacherOperations } from '../features/operations/TeacherOperations'
import { NotificationsPage } from '../features/operations/NotificationsPage'
import { GradePage } from '../features/grades/GradePage'
import { SubmissionPage, SubmissionHistoryPage } from '../features/submissions/SubmissionPages'
import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { Navigate, NavLink, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import {
  BookOpen,
  Crosshair,
  KeyRound,
  Bell,
  Archive,
  SlidersHorizontal,
  ShieldCheck,
  FileText,
  Braces,
} from 'lucide-react'
import { api, sessionKey, identityKey } from './runtime'
import { LoginPage } from '../features/auth/LoginPage'
import { PasswordPage } from '../features/auth/PasswordPage'
import {
  ProblemsPage,
  VersionsPage,
  CreateVersionPage,
  VersionPage,
} from '../features/problems/ProblemPages'
import { CoursesPage } from '../features/courses/CoursesPage'
import { CoursePage } from '../features/courses/CoursePage'
import { LogoutControl } from '../features/auth/LogoutControl'
import { AssignmentPage, CreateAssignmentPage } from '../features/assignments/AssignmentPages'
import { EditorPage } from '../features/assignments/EditorPage'
import { ExpiredDraftPage } from '../features/assignments/ExpiredDraftPage'
import { currentDraft } from '../features/assignments/drafts'
import { StatePanel } from '../components/ui/StatePanel'
const PublicPracticePage = lazy(() =>
  import('../features/problems/PracticePolicy').then((m) => ({ default: m.PublicPracticePage })),
)
const FeedbackCatalogsPage = lazy(() =>
  import('../features/learning/FeedbackPages').then((module) => ({
    default: module.FeedbackCatalogsPage,
  })),
)
const FeedbackDetailPage = lazy(() =>
  import('../features/learning/FeedbackPages').then((module) => ({
    default: module.FeedbackDetailPage,
  })),
)

const LearningPage = lazy(() => import('../features/learning/LearningPage'))

const TemplatesPage = lazy(() =>
  import('../features/learning/TemplatePages').then((module) => ({
    default: module.TemplatesPage,
  })),
)
const TemplatePage = lazy(() =>
  import('../features/learning/TemplatePages').then((module) => ({ default: module.TemplatePage })),
)

function Workspace() {
  const session = useQuery({ queryKey: sessionKey, queryFn: api.session, refetchInterval: 60_000 })
  const location = useLocation()
  if (session.isPending) return <StatePanel kind="loading" title="正在读取会话…" />
  if (session.isError)
    return (
      <StatePanel
        kind="error"
        title="连接暂不可用"
        description={session.error.message}
        onRetry={() => void session.refetch()}
      />
    )
  if (!session.data.authenticated || !session.data.user)
    return location.pathname.includes('/problems/') && currentDraft() ? (
      <ExpiredDraftPage />
    ) : (
      <Navigate to="/login" replace />
    )
  const user = session.data.user
  return (
    <div className="workspace">
      <a href="#main" className="skip-link">
        跳到主要内容
      </a>
      <aside className="sidebar">
        <NavLink className="brand" to="/courses">
          <BrandMark />
          <span>ASTRA</span>
        </NavLink>
        <p className="nav-label">学习工作区</p>
        <nav aria-label="主要导航">
          <NavLink to="/courses" className="nav-item">
            <BookOpen size={19} aria-hidden="true" />
            我的课程
          </NavLink>
          {(user.role === 'TEACHER' || user.role === 'ADMIN') && (
            <NavLink
              to={user.role === 'ADMIN' ? '/admin/feedback' : '/teacher/feedback'}
              className="nav-item"
            >
              <FileText size={19} aria-hidden="true" />
              {user.role === 'ADMIN' ? '全局固定帮助' : '固定帮助维护'}
            </NavLink>
          )}
          {(user.role === 'TEACHER' || user.role === 'ADMIN') && (
            <NavLink
              to={user.role === 'ADMIN' ? '/admin/hint-templates' : '/teacher/hint-templates'}
              className="nav-item"
            >
              <Braces size={19} aria-hidden="true" />
              {user.role === 'ADMIN' ? '全局提示模板' : '提示模板维护'}
            </NavLink>
          )}
          {user.role === 'STUDENT' && (
            <NavLink to="/learning" className="nav-item">
              <BookOpen size={19} aria-hidden="true" />
              我的学习
            </NavLink>
          )}
          {user.role !== 'STUDENT' && (
            <NavLink to="/retention" className="nav-item">
              <Archive size={19} aria-hidden="true" />
              课程留存
            </NavLink>
          )}
          {user.role === 'ADMIN' && (
            <NavLink to="/admin/operations/controls" className="nav-item">
              <SlidersHorizontal size={19} aria-hidden="true" />
              运行与应急
            </NavLink>
          )}
          <NavLink to="/notifications" className="nav-item">
            <Bell size={19} aria-hidden="true" />
            通知
          </NavLink>
          {user.role === 'ADMIN' && (
            <NavLink to="/admin/operations" end className="nav-item">
              <ShieldCheck size={19} aria-hidden="true" />
              平台管理
            </NavLink>
          )}
          <NavLink to="/account/password" className="nav-item">
            <KeyRound size={19} aria-hidden="true" />
            修改密码
          </NavLink>
        </nav>
        <div className="sidebar-note">
          <span className="small-rule" />
          <p>
            每一次尝试，
            <br />
            都是理解的开始。
          </p>
        </div>
        <div className="account">
          <span className="avatar" aria-hidden="true">
            {user.display_name.slice(0, 1)}
          </span>
          <div>
            <strong>{user.display_name}</strong>
            <span>{{ STUDENT: '学生', TEACHER: '教师', ADMIN: '管理员' }[user.role]}</span>
          </div>
          <LogoutControl userId={user.user_id} />
        </div>
      </aside>
      <div className="workspace-body">
        <header className="topbar">
          <div className="workspace-context">
            <span className="context-slash" aria-hidden="true">
              /
            </span>
            <strong>课程工作区</strong>
            <span className="platform-name">ASTRA · 编程教学平台</span>
          </div>
          <Crosshair className="topbar-mark" size={22} aria-hidden="true" />
          {__MOCK__ && <span className="mock-badge">演示 · 虚构数据</span>}
        </header>
        <main id="main" tabIndex={-1} className="main-content">
          {user.must_change_password ? (
            <PasswordPage forced />
          ) : user.role === 'ADMIN' &&
            location.pathname !== '/account/password' &&
            !location.pathname.startsWith('/admin/feedback') &&
            !location.pathname.startsWith('/admin/hint-templates') &&
            !location.pathname.startsWith('/admin/operations') &&
            location.pathname !== '/notifications' &&
            location.pathname !== '/retention' ? (
            <StatePanel
              kind="forbidden"
              title="请使用管理员工作区"
              description="课程列表仅面向学生和教师。"
            />
          ) : (
            <Suspense
              key={identityKey(session.data)}
              fallback={<StatePanel kind="loading" title="正在加载页面…" />}
            >
              <Outlet />
            </Suspense>
          )}
        </main>
      </div>
    </div>
  )
}
export function App() {
  return (
    <>
      <ButtonHints />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<Workspace />}>
          <Route path="/account/password" element={<PasswordPage />} />
          <Route path="/admin/operations" element={<AdminPage />} />
          <Route path="/admin/operations/controls" element={<ControlsPage />} />
          <Route path="/retention" element={<RetentionPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/assignments/:id/operations" element={<TeacherOperations />} />
          <Route path="/teacher/feedback" element={<FeedbackCatalogsPage />} />
          <Route path="/teacher/feedback/:id" element={<FeedbackDetailPage />} />
          <Route path="/admin/feedback" element={<FeedbackCatalogsPage />} />
          <Route path="/admin/feedback/:id" element={<FeedbackDetailPage />} />
          <Route path="/teacher/hint-templates" element={<TemplatesPage />} />
          <Route path="/teacher/hint-templates/:id" element={<TemplatePage />} />
          <Route path="/admin/hint-templates" element={<TemplatesPage />} />
          <Route path="/admin/hint-templates/:id" element={<TemplatePage />} />
          <Route path="/practice-problems/:id" element={<PublicPracticePage />} />
          <Route path="/learning" element={<LearningPage />} />
          <Route path="/courses" element={<CoursesPage />} />
          <Route path="/courses/:id" element={<CoursePage />} />
          <Route path="/courses/:id/assignments/new" element={<CreateAssignmentPage />} />
          <Route path="/assignments/:id" element={<AssignmentPage />} />
          <Route path="/assignments/:id/grades" element={<GradePage />} />
          <Route path="/assignments/:id/submissions" element={<SubmissionHistoryPage />} />
          <Route path="/submissions/:id" element={<SubmissionPage />} />
          <Route path="/assignments/:id/problems/:problemId" element={<EditorPage />} />
          <Route path="/courses/:id/problems" element={<ProblemsPage />} />
          <Route path="/teacher/problems/:id" element={<VersionsPage />} />
          <Route path="/teacher/problems/:id/new" element={<CreateVersionPage />} />
          <Route path="/teacher/problem-versions/:id" element={<VersionPage />} />
        </Route>
        <Route path="/" element={<Navigate to="/courses" replace />} />
        <Route
          path="*"
          element={
            <main className="not-found">
              <StatePanel kind="empty" title="页面不存在" description="请从课程入口继续。" />
              <a href="/courses">返回我的课程</a>
            </main>
          }
        />
      </Routes>
    </>
  )
}
