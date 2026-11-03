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
    sendSubmission: (
      body: components['schemas']['SubmissionCreate'],
      key: string,
      intent: 'FORMAL' | 'PRACTICE',
    ) =>
      unwrap(
        client.POST('/submissions', {
          body,
          params: { header: { 'Idempotency-Key': key, 'X-Submission-Intent': intent } },
        }),
      ),
    submission: (id: string) =>
      unwrap(
        client.GET('/submissions/{id}', {
          params: { path: { id } },
          headers: { 'X-Astra-Background': '1' },
        }),
      ),
    submissions: (
      assignment_id: string,
      problem_id?: string,
      verdict?: 'AC' | 'WA' | 'CE' | 'TLE' | 'RE' | 'SE',
      cursor?: string,
    ) =>
      unwrap(
        client.GET('/submissions', {
          params: { query: { assignment_id, problem_id, verdict, cursor } },
        }),
      ),
    submissionAttempts: (id: string, cursor?: string) =>
      unwrap(
        client.GET('/submissions/{id}/attempts', { params: { path: { id }, query: { cursor } } }),
      ),
    grades: (id: string, cursor?: string) =>
      unwrap(
        client.GET('/assignments/{id}/grades', { params: { path: { id }, query: { cursor } } }),
      ),
    publishGrades: (id: string, body: components['schemas']['PublishCommand']) =>
      unwrap(client.POST('/assignments/{id}/grades/publish', { params: { path: { id } }, body })),
    exportGrades: (id: string, grade_version: string) =>
      unwrap(
        client.GET('/assignments/{id}/grades.csv', {
          params: { path: { id }, query: { grade_version } },
          parseAs: 'text',
        }),
      ),
    rejudgePreview: (
      id: string,
      body: { problem_id: string; new_version_id: string; expected_revision: number },
    ) =>
      unwrap(client.POST('/assignments/{id}/rejudge-preview', { params: { path: { id } }, body })),
    createRejudge: (
      id: string,
      body: {
        new_version_id: string
        range_checksum: string
        expected_revision: number
        reason: string
      },
    ) => unwrap(client.POST('/assignments/{id}/rejudge', { params: { path: { id } }, body })),
    rejudge: (id: string) =>
      unwrap(
        client.GET('/rejudge-batches/{id}', {
          params: { path: { id } },
          headers: { 'X-Astra-Background': '1' },
        }),
      ),
    activateRejudge: (
      id: string,
      body: {
        expected_batch_revision: number
        expected_assignment_revision: number
        reason: string
      },
    ) => unwrap(client.POST('/rejudge-batches/{id}/activate', { params: { path: { id } }, body })),
    cancelRejudge: (id: string, body: { expected_revision: number; reason: string }) =>
      unwrap(client.POST('/rejudge-batches/{id}/cancel', { params: { path: { id } }, body })),
    retryRejudge: (id: string, body: { expected_revision: number; reason: string }) =>
      unwrap(client.POST('/rejudge-batches/{id}/retry', { params: { path: { id } }, body })),
    retrySubmission: (id: string, body: { expected_revision: number; reason: string }) =>
      unwrap(client.POST('/submissions/{id}/retry', { params: { path: { id } }, body })),
    adminHealth: () =>
      unwrap(client.GET('/admin/health', { headers: { 'X-Astra-Background': '1' } })),
    adminJobs: (cursor?: string) =>
      unwrap(client.GET('/admin/jobs', { params: { query: { cursor } } })),
    adminUsers: (cursor?: string) =>
      unwrap(client.GET('/admin/users', { params: { query: { cursor } } })),
    createUser: (body: components['schemas']['CreateUser']) =>
      unwrap(client.POST('/admin/users', { body, params: { header: { 'X-CSRF-Token': csrf! } } })),
    updateUser: (id: string, body: components['schemas']['UpdateUser']) =>
      unwrap(
        client.PATCH('/admin/users/{id}', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    resetUserPassword: (id: string, body: components['schemas']['ResetPassword']) =>
      checked(
        client.POST('/admin/users/{id}/reset-password', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    auditEvents: (cursor?: string) =>
      unwrap(client.GET('/admin/audit-events', { params: { query: { cursor } } })),
    incidents: (cursor?: string) =>
      unwrap(client.GET('/incidents', { params: { query: { cursor } } })),
    createIncident: (body: {
      started_at: string
      assignment_ids: string[]
      reason_code: string
      reason: string
      evidence_refs: string[]
      evidence_incomplete: boolean
    }) => unwrap(client.POST('/admin/incidents', { body })),
    recoverIncident: (
      id: string,
      body: { recovered_at: string; expected_revision: number; reason: string },
    ) => unwrap(client.PATCH('/admin/incidents/{id}/recovery', { params: { path: { id } }, body })),
    decideFairness: (
      id: string,
      body: {
        incident_id: string
        decision: 'EXTEND' | 'NO_IMPACT'
        reason: string
        expected_revision: number
      },
    ) =>
      unwrap(
        client.POST('/assignments/{id}/fairness-decisions', { params: { path: { id } }, body }),
      ),
    notifications: (cursor?: string) =>
      unwrap(
        client.GET('/notifications', {
          params: { query: { cursor } },
          headers: { 'X-Astra-Background': '1' },
        }),
      ),
    markNotificationRead: (id: string) =>
      unwrap(client.POST('/notifications/{id}/read', { params: { path: { id } } })),
    archiveCourse: (id: string, body: { expected_revision: number; reason: string }) =>
      unwrap(client.POST('/courses/{id}/archive', { params: { path: { id } }, body })),
    previewRetention: (body: { course_id: string; reason: string }) =>
      unwrap(client.POST('/admin/retention/previews', { body })),
    retention: (id: string) =>
      unwrap(client.GET('/admin/retention/{id}', { params: { path: { id } } })),
    confirmRetention: (
      id: string,
      body: { object_digest: string; expected_revision: number; reason: string },
    ) => unwrap(client.POST('/retention/{id}/confirm', { params: { path: { id } }, body })),
    executeRetention: (
      id: string,
      body: {
        object_digest: string
        confirmation_id: string
        expected_revision: number
        reason: string
      },
    ) => unwrap(client.POST('/admin/retention/{id}/execute', { params: { path: { id } }, body })),
    createHold: (body: { object_type: 'course'; object_id: string; reason: string }) =>
      unwrap(client.POST('/admin/holds', { body })),
    closeHold: (id: string, body: { expected_revision: number; reason: string }) =>
      unwrap(client.POST('/admin/holds/{id}/close', { params: { path: { id } }, body })),
    runtimeControl: () => unwrap(client.GET('/admin/runtime-config')),
    updateRuntimeControl: (body: {
      submission_enabled: boolean
      judge_enabled: boolean
      expected_revision: number
      reason: string
    }) => unwrap(client.PATCH('/admin/runtime-config', { body })),
    grantEmergency: (body: {
      incident_id: string
      scope: { course_id: string }
      expires_at: string
      reason: string
    }) => unwrap(client.POST('/admin/emergency-access', { body })),
    revokeEmergency: (id: string, body: { reason: string }) =>
      checked(
        client.POST('/admin/emergency-access/{id}/revoke', { params: { path: { id } }, body }),
      ),
    emergencySubmission: (id: string, submission_id: string) =>
      unwrap(
        client.GET('/admin/emergency-access/{id}/submission', {
          params: { path: { id }, query: { submission_id } },
        }),
      ),
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
    practiceProblem: (id: string) =>
      unwrap(client.GET('/practice-problems/{id}', { params: { path: { id } } })),
    practicePolicy: (id: string, body: components['schemas']['PracticePolicy']) =>
      unwrap(
        client.PATCH('/problems/{id}/practice-policy', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
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
    enqueuePreflight: (id: string, revision: number) =>
      unwrap(
        client.POST('/problem-versions/{id}/preflight', {
          body: { expected_revision: revision },
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    preflight: (id: string) =>
      unwrap(
        client.GET('/preflights/{id}', {
          params: { path: { id } },
          headers: { 'X-Astra-Background': '1' },
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
    feedbackCatalogs: (course_id?: string, cursor?: string) =>
      unwrap(
        client.GET('/feedback-catalogs', {
          params: {
            query: {
              ...(course_id ? { course_id } : {}),
              ...(cursor ? { cursor } : {}),
            },
          },
        }),
      ),
    createFeedback: (body: components['schemas']['CreateFeedback']) =>
      unwrap(
        client.POST('/feedback-catalogs', { body, params: { header: { 'X-CSRF-Token': csrf! } } }),
      ),
    feedbackDraft: (id: string) =>
      unwrap(client.GET('/feedback-catalogs/{id}/draft', { params: { path: { id } } })),
    saveFeedbackDraft: (id: string, body: components['schemas']['UpdateFeedback']) =>
      unwrap(
        client.PUT('/feedback-catalogs/{id}/draft', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    publishFeedback: (id: string, body: components['schemas']['PublishCommand']) =>
      unwrap(
        client.POST('/feedback-catalogs/{id}/publish', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    feedbackHistory: (id: string, cursor?: string) =>
      unwrap(
        client.GET('/feedback-catalogs/{id}/versions', {
          params: { path: { id }, query: { ...(cursor ? { cursor } : {}) } },
        }),
      ),
    feedbackVersion: (id: string, version: number) =>
      unwrap(
        client.GET('/feedback-catalogs/{id}/versions/{version}', {
          params: { path: { id, version } },
        }),
      ),
    reviewItems: (context: 'FORMAL' | 'PRACTICE', course_id?: string, cursor?: string) =>
      unwrap(client.GET('/review-items', { params: { query: { context, course_id, cursor } } })),
    recommendations: (course_id?: string) =>
      unwrap(client.GET('/recommendations', { params: { query: { course_id } } })),
    hintHistory: (cursor?: string) =>
      unwrap(client.GET('/ai-hints', { params: { query: { cursor } } })),
    createHint: (body: components['schemas']['CreateHint']) =>
      unwrap(client.POST('/ai-hints', { body, params: { header: { 'X-CSRF-Token': csrf! } } })),
    hint: (hint_id: string) =>
      unwrap(
        client.GET('/ai-hints/{hint_id}', {
          params: { path: { hint_id }, header: { 'X-Astra-Background': '1' } },
        }),
      ),
    rateHint: (id: string, body: components['schemas']['HintRating']) =>
      unwrap(
        client.POST('/ai-hints/{id}/feedback', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    templates: (course_id?: string, cursor?: string) =>
      unwrap(
        client.GET('/hint-templates', {
          params: {
            query: {
              ...(course_id ? { course_id } : {}),
              ...(cursor ? { cursor } : {}),
            },
          },
        }),
      ),
    createTemplate: (body: components['schemas']['CreateTemplate']) =>
      unwrap(
        client.POST('/hint-templates', { body, params: { header: { 'X-CSRF-Token': csrf! } } }),
      ),
    templateDraft: (id: string) =>
      unwrap(client.GET('/hint-templates/{id}/draft', { params: { path: { id } } })),
    saveTemplate: (id: string, body: components['schemas']['UpdateTemplate']) =>
      unwrap(
        client.PUT('/hint-templates/{id}/draft', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    publishTemplate: (id: string, body: components['schemas']['PublishCommand']) =>
      unwrap(
        client.POST('/hint-templates/{id}/publish', {
          body,
          params: { path: { id }, header: { 'X-CSRF-Token': csrf! } },
        }),
      ),
    templateHistory: (id: string, cursor?: string) =>
      unwrap(
        client.GET('/hint-templates/{id}/versions', {
          params: { path: { id }, query: { ...(cursor ? { cursor } : {}) } },
        }),
      ),
    templateVersion: (id: string, version: number) =>
      unwrap(
        client.GET('/hint-templates/{id}/versions/{version}', {
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
