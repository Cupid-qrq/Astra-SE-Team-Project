import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, clearSession } from '../../app/runtime'
import { Field } from '../../components/ui/Field'
import { Button } from '../../components/ui/Button'

export function PasswordPage({ forced = false }: { forced?: boolean }) {
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const mutation = useMutation({
    mutationFn: api.changePassword,
    onSuccess: () => {
      clearSession()
      navigate('/login', { replace: true })
    },
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const current_password = String(data.get('current_password'))
    const new_password = String(data.get('new_password'))
    if (new_password !== data.get('confirmation')) {
      setError('两次输入的新密码不一致。')
      return
    }
    if ([...new_password].length < 12 || [...new_password].length > 128) {
      setError('密码长度为 12–128 个字符。')
      return
    }
    setError('')
    mutation.mutate({ current_password, new_password })
  }
  return (
    <section className="management-panel">
      <h1>{forced ? '修改初始密码' : '修改密码'}</h1>
      <p>
        {forced ? '首次登录或重置后，请设置个人密码。' : '请输入当前密码和新密码。'}
        保存后需要重新登录，其他设备上的旧会话也会失效。
      </p>
      <form onSubmit={submit}>
        <Field
          label="当前密码"
          name="current_password"
          type="password"
          autoComplete="current-password"
          required
          minLength={12}
          maxLength={128}
        />
        <Field
          label="新密码"
          name="new_password"
          type="password"
          autoComplete="new-password"
          required
          minLength={12}
          maxLength={128}
        />
        <Field
          label="确认新密码"
          name="confirmation"
          type="password"
          autoComplete="new-password"
          required
        />
        {(error || mutation.error) && (
          <p role="alert" className="form-error">
            {error || mutation.error?.message}
          </p>
        )}
        <Button type="submit" busy={mutation.isPending}>
          保存并重新登录
        </Button>
      </form>
    </section>
  )
}
