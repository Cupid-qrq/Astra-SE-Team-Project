import { describe, expect, it, vi } from 'vitest'
import { createApiClient, ApiError } from './client'

const session = (token: string) => ({
  authenticated: false,
  user: null,
  csrf_token: token,
  server_time: '2026-10-24T00:00:00.000Z',
})
describe('客户端会话与错误边界', () => {
  it('旧请求的延迟401不能清除新登录会话', async () => {
    let complete!: (value: Response) => void
    const delayed = new Promise<Response>((resolve) => {
      complete = resolve
    })
    const expired = vi.fn()
    const api = createApiClient({
      baseUrl: 'http://localhost/api/v1',
      onUnauthorized: expired,
      fetch: async (request) => {
        if (request.url.endsWith('/courses')) return delayed
        if (request.url.endsWith('/auth/session')) return Response.json(session('current-token'))
        return Response.json({ user: {} })
      },
    })
    const old = api.courses().catch((error) => error)
    await api.login({ login_name: 'student', password: 'ExamplePass123' })
    complete(
      Response.json(
        {
          code: 'UNAUTHENTICATED',
          message: 'old session',
          request_id: 'old',
          retryable: false,
          retry_after_seconds: null,
          field_errors: [],
        },
        { status: 401 },
      ),
    )
    expect(await old).toMatchObject({ code: 'STALE_RESPONSE' })
    expect(expired).not.toHaveBeenCalled()
  })
  it('旧会话成功响应不能覆盖新登录后的CSRF', async () => {
    let complete!: (value: Response) => void
    const delayed = new Promise<Response>((resolve) => {
      complete = resolve
    })
    let reads = 0
    const tokens: (string | null)[] = []
    const api = createApiClient({
      baseUrl: 'http://localhost/api/v1',
      fetch: async (request) => {
        if (request.url.endsWith('/auth/session'))
          return ++reads === 1 ? delayed : Response.json(session('new-token'))
        tokens.push(request.headers.get('X-CSRF-Token'))
        return request.url.endsWith('/auth/logout')
          ? new Response(null, { status: 204 })
          : Response.json({ user: {} })
      },
    })
    const old = api.session().catch((error) => error)
    await api.login({ login_name: 'student', password: 'ExamplePass123' })
    complete(Response.json(session('stale-token')))
    expect(await old).toMatchObject({ code: 'STALE_RESPONSE' })
    await api.logout()
    expect(tokens).toEqual(['new-token', 'new-token'])
  })
  it('成功状态的非 JSON 响应也转换为稳定错误', async () => {
    const api = createApiClient({
      baseUrl: 'http://localhost/api/v1',
      fetch: async () => new Response('<html>INTERNAL_PROXY</html>', { status: 200 }),
    })
    await expect(api.courses()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
  })
  it('登录先取预会话 CSRF，登录后刷新轮换令牌，写请求不重试', async () => {
    const requests: Request[] = []
    let sessions = 0
    const transport = vi.fn(async (request: Request) => {
      requests.push(request)
      if (request.url.endsWith('/auth/session'))
        return Response.json(session(++sessions === 1 ? 'before' : 'after'))
      if (request.url.endsWith('/auth/logout')) return new Response(null, { status: 204 })
      return Response.json({ user: {} })
    })
    const api = createApiClient({ baseUrl: 'http://localhost/api/v1', fetch: transport })
    await api.login({ login_name: 'student', password: 'ExamplePass123' })
    await api.logout()
    expect(requests[1].headers.get('X-CSRF-Token')).toBe('before')
    expect(requests[3].headers.get('X-CSRF-Token')).toBe('after')
    expect(requests.every((request) => request.credentials === 'same-origin')).toBe(true)
    expect(transport).toHaveBeenCalledTimes(4)
  })
  it('401 撤销客户端令牌并通知清除账户数据', async () => {
    const expired = vi.fn()
    const api = createApiClient({
      baseUrl: 'http://localhost/api/v1',
      onUnauthorized: expired,
      fetch: async () =>
        Response.json(
          {
            code: 'UNAUTHENTICATED',
            message: '请重新登录',
            request_id: 'req',
            retryable: false,
            retry_after_seconds: null,
            field_errors: [],
          },
          { status: 401 },
        ),
    })
    await expect(api.courses()).rejects.toMatchObject({ status: 401, code: 'UNAUTHENTICATED' })
    expect(expired).toHaveBeenCalledOnce()
  })
  it('非 JSON 网关错误不泄漏 HTML、堆栈或自动重试', async () => {
    const transport = vi.fn(async () => new Response('<html>SECRET_TRACE</html>', { status: 503 }))
    const api = createApiClient({ baseUrl: 'http://localhost/api/v1', fetch: transport })
    await expect(api.courses()).rejects.toMatchObject({ code: 'SERVICE_UNAVAILABLE', status: 503 })
    expect(transport).toHaveBeenCalledOnce()
  })
  it('网络失败返回稳定错误而不是原始内部异常', async () => {
    const api = createApiClient({
      baseUrl: 'http://localhost/api/v1',
      fetch: async () => {
        throw new Error('SECRET_HOST')
      },
    })
    try {
      await api.courses()
      expect.fail('应当拒绝')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as Error).message).not.toContain('SECRET_HOST')
    }
  })
})
