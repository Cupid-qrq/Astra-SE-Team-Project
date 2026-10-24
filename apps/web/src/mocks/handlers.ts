import { http, HttpResponse } from 'msw'
import { assignments, courses, user } from './fixtures'
import type { components } from '../lib/api/schema'

// Deliberately limited transport fixture. This is not an authorization service.
// Per-tab state survives refresh, and never stores passwords, tokens or source code.
const state = { login: '', csrf: crypto.randomUUID(), unavailable: false }
const readLogin = () =>
  typeof sessionStorage === 'undefined'
    ? state.login
    : sessionStorage.getItem('astra.mock.login') || ''
const setLogin = (login: string) => {
  state.login = login
  if (typeof sessionStorage !== 'undefined') sessionStorage.setItem('astra.mock.login', login)
}
function error(status: number, code: string, message: string) {
  const retryable = status === 503
  const body: components['schemas']['Error'] = {
    code,
    message,
    request_id: crypto.randomUUID(),
    retryable,
    retry_after_seconds: retryable ? 1 : null,
    field_errors: [],
  }
  return HttpResponse.json(body, {
    status,
    headers: {
      'X-Request-Id': body.request_id,
      'Cache-Control': 'no-store',
      ...(retryable ? { 'Retry-After': '1' } : {}),
    },
  })
}
function json<T>(data: T) {
  return HttpResponse.json(data as never, {
    headers: { 'Cache-Control': 'no-store', 'X-Request-Id': crypto.randomUUID() },
  })
}
function guard() {
  return readLogin() ? undefined : error(401, 'UNAUTHENTICATED', '请重新登录。')
}
export const handlers = [
  http.get('/api/v1/auth/session', () =>
    json({
      authenticated: !!readLogin(),
      user: readLogin()
        ? {
            ...user,
            login_name: readLogin(),
            role: readLogin() === 'demo_teacher' ? 'TEACHER' : 'STUDENT',
          }
        : null,
      csrf_token: state.csrf,
      server_time: new Date().toISOString(),
    } satisfies components['schemas']['Session']),
  ),
  http.post('/api/v1/auth/login', async ({ request }) => {
    if (request.headers.get('X-CSRF-Token') !== state.csrf)
      return error(403, 'FORBIDDEN', '登录状态已变更，请重试。')
    const body = (await request.json()) as components['schemas']['Login']
    if (
      !['demo_student', 'demo_teacher', 'demo_expired', 'demo_unavailable', 'demo_empty'].includes(
        body.login_name,
      ) ||
      body.password !== 'ExamplePass123'
    )
      return error(401, 'UNAUTHENTICATED', '账号或密码不正确。')
    setLogin(body.login_name)
    state.csrf = crypto.randomUUID()
    state.unavailable = body.login_name === 'demo_unavailable'
    return json({ user: { ...user, login_name: readLogin() } })
  }),
  http.post('/api/v1/auth/logout', ({ request }) => {
    const denied = guard()
    if (denied) return denied
    if (request.headers.get('X-CSRF-Token') !== state.csrf)
      return error(403, 'FORBIDDEN', '会话校验失败。')
    setLogin('')
    state.csrf = crypto.randomUUID()
    return new HttpResponse(null, { status: 204 })
  }),
  http.get('/api/v1/courses', () => {
    const denied = guard()
    if (denied) return denied
    if (state.unavailable) {
      state.unavailable = false
      return error(503, 'PERSISTENCE_UNAVAILABLE', '服务暂时不可用，请稍后重试。')
    }
    return json({ items: readLogin() === 'demo_empty' ? [] : courses, next_cursor: null })
  }),
  http.get('/api/v1/courses/:id', ({ params }) => {
    if (readLogin() === 'demo_expired') {
      setLogin('')
      return error(401, 'UNAUTHENTICATED', '会话已失效，请重新登录。')
    }
    const denied = guard()
    if (denied) return denied
    const course = courses.find((item) => item.course_id === params.id)
    return course ? json(course) : error(404, 'NOT_FOUND', '课程不可用。')
  }),
  http.get('/api/v1/courses/:id/assignments', ({ params }) => {
    const denied = guard()
    if (denied) return denied
    if (!courses.some((item) => item.course_id === params.id))
      return error(404, 'NOT_FOUND', '课程不可用。')
    return json({
      items: assignments.filter((item) => item.course_id === params.id),
      next_cursor: null,
    })
  }),
  http.all('/api/v1/*', () => error(503, 'MOCK_NOT_IMPLEMENTED', '此接口尚未接入当前演示。')),
]
