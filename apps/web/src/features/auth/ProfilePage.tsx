import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, sessionKey } from '../../app/runtime'
import { MotionToggle } from '../../components/ui/MotionEffects'

export function ProfilePage() {
  const [params, setParams] = useSearchParams()
  const settings = params.get('tab') === 'settings'
  const { data } = useQuery({ queryKey: sessionKey, queryFn: api.session })
  const [masked, setMasked] = useState(
    () => document.documentElement.dataset.privateName === 'true',
  )
  const user = data?.user
  if (!user) return null
  function changeMask(value: boolean) {
    setMasked(value)
    document.documentElement.dataset.privateName = String(value)
    try {
      localStorage.setItem('astra.privateName', String(value))
    } catch {
      /* Session preference remains usable. */
    }
  }
  return (
    <div className="profile-page stack">
      <section className="profile-hero">
        <span className="profile-avatar" aria-hidden="true">
          {masked ? '·' : user.display_name.slice(0, 1)}
        </span>
        <div>
          <p>个人主页</p>
          <h1>{masked ? '我的主页' : user.display_name}</h1>
          <p>
            {{ STUDENT: '学生', TEACHER: '教师', ADMIN: '管理员' }[user.role]} ·
            每一次尝试，都是理解的开始。
          </p>
        </div>
      </section>
      <nav className="section-tabs" aria-label="个人主页栏目">
        <Link to="/account/profile" aria-current={!settings ? 'page' : undefined}>
          概览
        </Link>
        <Link to="/account/profile?tab=settings" aria-current={settings ? 'page' : undefined}>
          显示与隐私设置
        </Link>
      </nav>
      <div className="profile-grid">
        {!settings && (
          <>
            <section className="panel">
              <h2>常用入口</h2>
              <p>从这里回到你的课程与消息。</p>
              <div className="profile-links">
                <Link to={user.role === 'ADMIN' ? '/admin/operations' : '/courses'}>
                  {user.role === 'ADMIN' ? '平台管理' : '我的课程'} →
                </Link>
                <Link to="/notifications">我的通知 →</Link>
                {user.role === 'STUDENT' && <Link to="/learning">错题与学习提示 →</Link>}
                <Link to="/account/password">修改密码 →</Link>
              </div>
            </section>
            <section className="panel">
              <h2>使用指南</h2>
              <ol className="workflow-steps">
                {{
                  STUDENT: [
                    ['选择课程', '进入课程查看作业和截止时间。'],
                    ['完成练习', '读题、编写代码，再查看评测结果。'],
                    ['理解反馈', '先看判题帮助，再按需请求 AI 提示。'],
                  ],
                  TEACHER: [
                    ['准备课程', '创建课程，添加成员并维护题目。'],
                    ['安排作业', '核对题目、分值与时间，预检通过后发布。'],
                    ['跟进学习', '查看成绩，维护判题帮助和 AI 辅导要求。'],
                  ],
                  ADMIN: [
                    ['查看运行状态', '从平台管理查看服务与任务情况。'],
                    ['维护账号', '按实际需要创建或调整账号，并填写操作理由。'],
                    ['处理异常', '核对故障记录，按范围申请应急访问。'],
                  ],
                }[user.role].map(([title, description]) => (
                  <li key={title}>
                    <strong>{title}</strong>
                    <p>{description}</p>
                  </li>
                ))}
              </ol>
              <button
                className="button button-secondary"
                onClick={() => setParams({ tab: 'settings' })}
                title="打开动效和姓名显示设置"
              >
                管理显示偏好
              </button>
            </section>
          </>
        )}
        {settings && (
          <section className="panel profile-settings">
            <h2>显示与隐私设置</h2>
            <div className="preference-row">
              <div>
                <h3>界面动效</h3>
                <p>默认开启粒子与页面过渡，遵循系统减少动态设置。</p>
              </div>
              <MotionToggle />
            </div>
            <div className="preference-row">
              <label htmlFor="private-name">
                <strong>遮住当前浏览器中的姓名</strong>
                <p>在共用屏幕时隐藏侧栏与个人主页中的姓名。课程和成绩页面仍按实际内容显示。</p>
              </label>
              <input
                id="private-name"
                type="checkbox"
                checked={masked}
                onChange={(e) => changeMask(e.target.checked)}
              />
            </div>
            <p className="muted">
              以上设置保存在当前浏览器，供这台设备使用，不改变其他用户的访问权限。
            </p>
          </section>
        )}
      </div>
      <section className="panel">
        <h2>你的数据如何使用</h2>
        <p>个人主页仅供当前登录账号查看。课程、提交与成绩的访问由平台按角色和课程权限决定。</p>
        <p>AI 提示需要在请求时明确同意发送代码和公开题面；这里的显示设置不会替你同意代码外发。</p>
      </section>
    </div>
  )
}
