import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type Session = components['schemas']['Session']
export type User = components['schemas']['User']
export type ApiProblem = components['schemas']['Error']
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public detail?: ApiProblem,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}
type Options = {
  baseUrl?: string
  fetch?: (request: Request) => Promise<Response>
  onUnauthorized?: () => void
}
export function createApiClient({
  baseUrl = '/api/v1',
  fetch: transport,
  onUnauthorized,
}: Options = {}) {
  let csrf: string | undefined
  let authEpoch = 0
  let lastIdentity: string | undefined
  const requestEpochs = new WeakMap<Request, number>()
  const client = createClient<paths>({
    baseUrl,
    credentials: 'same-origin',
    ...(transport ? { fetch: transport } : {}),
  })
  client.use({
    onRequest({ request }) {
      requestEpochs.set(request, authEpoch)
      if (!['GET', 'HEAD'].includes(request.method) && csrf)
        request.headers.set('X-CSRF-Token', csrf)
      return request
    },
    async onResponse({ request, response }) {
      if (requestEpochs.get(request) !== authEpoch)
        throw new ApiError(0, 'STALE_RESPONSE', '会话已变更，请重新操作。')
      if (response.ok) return response
      if (response.status === 401) {
        authEpoch += 1
        csrf = undefined
        onUnauthorized?.()
      }
      let detail: ApiProblem | undefined
      try {
        const value: unknown = await response.clone().json()
        if (
          typeof value === 'object' &&
          value !== null &&
          'code' in value &&
          typeof value.code === 'string' &&
          'message' in value &&
          typeof value.message === 'string' &&
          'request_id' in value &&
          typeof value.request_id === 'string'
        )
          detail = value as ApiProblem
      } catch {
        /* A proxy may return HTML. Never expose the raw body. */
      }
      throw new ApiError(
        response.status,
        detail?.code || 'SERVICE_UNAVAILABLE',
        detail?.message || '服务暂时不可用，请稍后重试。',
        detail,
      )
    },
    onError({ error }) {
      return error instanceof ApiError
        ? error
        : new ApiError(0, 'NETWORK_ERROR', '连接失败，请检查网络后重试。')
    },
  })
  async function checked<T>(result: Promise<T>): Promise<T> {
    try {
      return await result
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(0, 'INVALID_RESPONSE', '服务响应格式无效，请稍后重试。')
    }
  }
  async function unwrap<T>(result: Promise<{ data?: T; response: Response }>): Promise<T> {
    const { data } = await checked(result)
    if (data === undefined)
      throw new ApiError(0, 'INVALID_RESPONSE', '服务响应不完整，请稍后重试。')
    return data
  }
  async function session() {
    const startedEpoch = authEpoch
    const value = await unwrap(client.GET('/auth/session'))
    if (startedEpoch !== authEpoch)
      throw new ApiError(0, 'STALE_RESPONSE', '会话已变更，请重新操作。')
    const identity =
      value.authenticated && value.user
        ? `${value.user.user_id}:${value.user.role}:${value.user.status}:${value.user.revision}`
        : 'anonymous'
    if (lastIdentity !== undefined && lastIdentity !== identity) authEpoch += 1
    lastIdentity = identity
    csrf = value.csrf_token
    return value
  }
  // Browsers supply Origin. Token values stay in memory and are replaced after login.
  async function login(body: components['schemas']['Login']) {
    authEpoch += 1
    csrf = undefined
    await session()
    await checked(
      client.POST('/auth/login', { body, params: { header: { 'X-CSRF-Token': csrf! } } }),
    )
    return session()
  }
  async function logout() {
    authEpoch += 1
    if (!csrf) await session()
    await checked(client.POST('/auth/logout', { params: { header: { 'X-CSRF-Token': csrf! } } }))
    csrf = undefined
  }
  return {
    session,
    login,
    logout,
    assignment: (id: string, background = false) =>
      unwrap(
        client.GET('/assignments/{id}', {
          params: { path: { id } },
          headers: background ? { 'X-Astra-Background': '1' } : undefined,
        }),
      ),
    assignmentProblem: (id: string, problem_id: string) =>
      unwrap(
        client.GET('/assignments/{id}/problems/{problem_id}', {
          params: { path: { id, problem_id } },
        }),
      ),
    createAssignment: (body: components['schemas']['CreateAssignment']) =>
      unwrap(client.POST('/assignments', { body, params: { header: { 'X-CSRF-Token': csrf! } } })),
    updateAssignment: (id: string, body: components['schemas']['UpdateAssignment']) =>
      unwrap(
        client.PATCH('/assignments/{id}', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    publishAssignment: (id: string, body: components['schemas']['PublishCommand']) =>
      unwrap(
        client.POST('/assignments/{id}/publish', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    extendAssignment: (id: string, body: components['schemas']['DeadlineCommand']) =>
      unwrap(
        client.PATCH('/assignments/{id}/deadline', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    assignmentPolicy: (id: string, body: components['schemas']['PolicyCommand']) =>
      unwrap(
        client.PATCH('/assignments/{id}/ai-policy', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    profiles: () => unwrap(client.GET('/problem-profiles')),
    problems: (id: string, cursor?: string) =>
      unwrap(
        client.GET('/courses/{id}/problems', {
          params: { path: { id }, query: { ...(cursor ? { cursor } : {}) } },
        }),
      ),
    createProblem: (body: components['schemas']['CreateProblem']) =>
      unwrap(client.POST('/problems', { body, params: { header: { 'X-CSRF-Token': csrf! } } })),
    versions: (id: string, cursor?: string) =>
      unwrap(
        client.GET('/problems/{id}/versions', {
          params: { path: { id }, query: { ...(cursor ? { cursor } : {}) } },
        }),
      ),
    version: (id: string) =>
      unwrap(client.GET('/problem-versions/{id}', { params: { path: { id } } })),
    createVersion: (body: components['schemas']['CreateVersion']) =>
      unwrap(
        client.POST('/problem-versions', { body, params: { header: { 'X-CSRF-Token': csrf! } } }),
      ),
    updateVersion: (id: string, body: components['schemas']['UpdateVersion']) =>
      unwrap(
        client.PATCH('/problem-versions/{id}', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    testcases: (id: string) =>
      unwrap(client.GET('/problem-versions/{id}/testcases', { params: { path: { id } } })),
    references: (id: string) =>
      unwrap(client.GET('/problem-versions/{id}/references', { params: { path: { id } } })),
    putTestcase: (id: string, order: number, body: components['schemas']['PutTestcase']) =>
      unwrap(
        client.PUT('/problem-versions/{id}/testcases/{order}', {
          body,
          params: { path: { id, order }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    deleteTestcase: (id: string, order: number, body: components['schemas']['RevisionCommand']) =>
      checked(
        client.DELETE('/problem-versions/{id}/testcases/{order}', {
          body,
          params: { path: { id, order }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    putReference: (
      id: string,
      language_key: 'cpp17' | 'python3',
      body: components['schemas']['PutReference'],
    ) =>
      unwrap(
        client.PUT('/problem-versions/{id}/references/{language_key}', {
          body,
          params: { path: { id, language_key }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    publishVersion: (id: string, body: components['schemas']['PublishVersion']) =>
      unwrap(
        client.POST('/problem-versions/{id}/publish', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    changePassword: (body: components['schemas']['Password']) =>
      checked(
        client.POST('/auth/password', { body, params: { header: { 'X-CSRF-Token': csrf! } } }),
      ),
    createCourse: (body: components['schemas']['CreateCourse']) =>
      unwrap(client.POST('/courses', { body, params: { header: { 'X-CSRF-Token': csrf! } } })),
    updateCourse: (id: string, body: components['schemas']['UpdateCourse']) =>
      unwrap(
        client.PATCH('/courses/{id}', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    members: (id: string, cursor?: string) =>
      unwrap(
        client.GET('/courses/{id}/members', {
          params: { path: { id }, query: { ...(cursor ? { cursor } : {}) } },
        }),
      ),
    updateMember: (id: string, user_id: string, body: components['schemas']['UpdateMember']) =>
      unwrap(
        client.PUT('/courses/{id}/members/{user_id}', {
          body,
          params: { path: { id, user_id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    courses: (cursor?: string) =>
      unwrap(client.GET('/courses', { params: { query: { ...(cursor ? { cursor } : {}) } } })),
    course: (id: string) => unwrap(client.GET('/courses/{id}', { params: { path: { id } } })),
    submissionFeedback: (id: string) =>
      unwrap(client.GET('/submissions/{id}/feedback', { params: { path: { id } } })),
    feedbackVersion: (id: string, version: number) =>
      unwrap(
        client.GET('/feedback-catalogs/{id}/versions/{version}', {
          params: { path: { id, version } },
        }),
      ),
    assignments: (id: string, cursor?: string) =>
      unwrap(
        client.GET('/courses/{id}/assignments', {
          params: { path: { id }, query: { ...(cursor ? { cursor } : {}) } },
        }),
      ),
  }
}
