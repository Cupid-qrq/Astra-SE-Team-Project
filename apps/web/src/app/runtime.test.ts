import { QueryObserver } from '@tanstack/react-query'
import { expect, it } from 'vitest'
import { clearSession, queryClient, sessionKey, reconcileSession } from './runtime'
import { user } from '../mocks/fixtures'

it.each(['identity', 'role', 'anonymous'])('成功会话刷新发生%s变化也清除旧账户数据', (change) => {
  const old = {
    authenticated: true,
    user,
    csrf_token: 'old',
    server_time: '2026-10-24T00:00:00.000Z',
  }
  queryClient.setQueryData(sessionKey, old)
  queryClient.setQueryData(['courses'], { items: ['PRIVATE_OLD_USER'] })
  const next = {
    ...old,
    authenticated: change !== 'anonymous',
    user:
      change === 'anonymous'
        ? null
        : {
            ...user,
            user_id: change === 'identity' ? 'other-user' : user.user_id,
            role: change === 'role' ? ('TEACHER' as const) : user.role,
          },
  }
  expect(reconcileSession(next)).toEqual(next)
  expect(queryClient.getQueryData(['courses'])).toBeUndefined()
  queryClient.clear()
})

it('会话失效通知已挂载观察者，不留下旧用户视图', () => {
  queryClient.setQueryData(sessionKey, {
    authenticated: true,
    user,
    csrf_token: 'old',
    server_time: '2026-10-24T00:00:00.000Z',
  })
  queryClient.setQueryData(['courses'], { items: ['private'] })
  const observer = new QueryObserver(queryClient, { queryKey: sessionKey, enabled: false })
  const unsubscribe = observer.subscribe(() => {})
  clearSession()
  expect(observer.getCurrentResult().data).toMatchObject({ authenticated: false, user: null })
  expect(queryClient.getQueryData(['courses'])).toBeUndefined()
  unsubscribe()
  queryClient.clear()
})
