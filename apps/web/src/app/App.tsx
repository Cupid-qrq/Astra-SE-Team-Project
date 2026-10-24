import { useQuery } from '@tanstack/react-query'
import { Navigate, NavLink, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { BookOpen, ChevronRight } from 'lucide-react'
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
          <span className="brand-mark" aria-hidden="true">
            a
          </span>
          Astra
        </NavLink>
        <p className="nav-label">学习工作区</p>
        <nav aria-label="主要导航">
          <NavLink to="/courses" className="nav-item">
            <BookOpen size={19} aria-hidden="true" />
            我的课程
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
          <span>Astra</span>
          <ChevronRight size={14} aria-hidden="true" />
          <span>课程工作区</span>
          {__MOCK__ && <span className="mock-badge">演示 · 虚构数据</span>}
        </header>
        <main id="main" tabIndex={-1} className="main-content">
          {user.must_change_password ? (
            <PasswordPage />
          ) : user.role === 'ADMIN' ? (
            <StatePanel
              kind="forbidden"
              title="请使用管理员工作区"
              description="课程列表仅面向学生和教师。"
            />
          ) : (
            <Outlet key={identityKey(session.data)} />
          )}
        </main>
      </div>
    </div>
  )
}
export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Workspace />}>
        <Route path="/courses" element={<CoursesPage />} />
        <Route path="/courses/:id" element={<CoursePage />} />
        <Route path="/courses/:id/assignments/new" element={<CreateAssignmentPage />} />
        <Route path="/assignments/:id" element={<AssignmentPage />} />
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
  )
}
