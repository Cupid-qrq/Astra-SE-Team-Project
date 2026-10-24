import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, BookOpen } from 'lucide-react'
import { api, queryClient, sessionKey } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'

export function LoginPage() {
  const navigate = useNavigate()
  const [fields, setFields] = useState<Record<string, string>>({})
  const mutation = useMutation({
    mutationFn: api.login,
    onSuccess: (session) => {
      queryClient.clear()
      queryClient.setQueryData(sessionKey, session)
      navigate('/courses', { replace: true })
    },
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const login_name = String(form.get('login_name') || '')
    const password = String(form.get('password') || '')
    const errors: Record<string, string> = {}
    if (!/^[A-Za-z0-9_]{3,32}$/.test(login_name))
      errors.login_name = '请输入 3–32 位字母、数字或下划线。'
    if ([...password].length < 12 || [...password].length > 128)
      errors.password = '密码长度为 12–128 个字符。'
    setFields(errors)
    if (Object.keys(errors).length) {
      ;(event.currentTarget.elements.namedItem(Object.keys(errors)[0]) as HTMLElement)?.focus()
      return
    }
    mutation.mutate({ login_name, password })
  }
  return (
    <main className="login-page">
      <section className="login-intro">
        <a className="brand" href="/login">
          <span className="brand-mark" aria-hidden="true">
            a
          </span>
          Astra
        </a>
        <div>
          <BookOpen size={36} strokeWidth={1.25} aria-hidden="true" />
          <h1>把思考写进代码。</h1>
          <p>
            从一道题开始，
            <br />
            在每一次尝试中理解更多。
          </p>
        </div>
        <span className="intro-footer">课程 · 练习 · 反馈</span>
      </section>
      <section className="login-panel">
        <div className="login-form">
          <h2>欢迎回来</h2>
          <p className="muted">登录你的课程工作区。</p>
          <form noValidate onSubmit={submit}>
            <Field
              label="账号"
              name="login_name"
              autoComplete="username"
              placeholder="请输入账号"
              error={fields.login_name}
            />
            <Field
              label="密码"
              name="password"
              type="password"
              autoComplete="current-password"
              placeholder="请输入密码"
              error={fields.password}
            />
            {mutation.error && (
              <p className="form-error" role="alert">
                {mutation.error.message}
              </p>
            )}
            <Button type="submit" busy={mutation.isPending}>
              登录
              <ArrowRight size={16} aria-hidden="true" />
            </Button>
          </form>
          <p className="login-help">账号由课程管理员提供。无法登录时，请联系任课教师。</p>
          {__MOCK__ && (
            <aside className="demo-note">
              演示环境 · 仅含虚构数据
              <br />
              账号 demo_student · 密码 ExamplePass123
            </aside>
          )}
        </div>
      </section>
    </main>
  )
}
