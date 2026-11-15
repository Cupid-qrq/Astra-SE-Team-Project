import { NavLink, useLocation } from 'react-router-dom'
export function LearningSupportNav() {
  const { pathname, search } = useLocation()
  if (!/^\/(teacher|admin)\/(feedback|hint-templates)(\/|$)/.test(pathname)) return null
  const root = pathname.startsWith('/admin/') ? '/admin' : '/teacher'
  const course = new URLSearchParams(search).get('course_id')
  const suffix = course ? `?course_id=${encodeURIComponent(course)}` : ''
  return (
    <section className="support-navigation" aria-label="学习辅导">
      <nav className="section-tabs" aria-label="辅导方式">
        <NavLink to={`${root}/feedback${suffix}`}>判题帮助</NavLink>
        <NavLink to={`${root}/hint-templates${suffix}`}>AI 辅导设置</NavLink>
      </nav>
      <p>
        {pathname.includes('/feedback')
          ? '学生直接阅读的错误说明与检查清单，不需要调用 AI。'
          : '告诉 AI 如何引导学生思考。学生请求提示时，AI 根据这些要求生成建议。'}
      </p>
    </section>
  )
}
