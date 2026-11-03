import type { ComponentType } from 'react'
import { ApiError } from '../../lib/api/client'
import { api } from '../../app/runtime'
import type { components } from '../../lib/api/schema'

export type Preflight = components['schemas']['PreflightReceipt']
export type PreflightStatus = components['schemas']['PreflightStatus']

export type SubmissionIntent = {
  idempotency_key: string
  assignment_id: string
  problem_id: string
  language_key: 'cpp17' | 'python3'
  code: string
  code_sha256: string
  intent: 'FORMAL' | 'PRACTICE'
}
export type SubmissionReceipt = {
  submission_id: string
  mode: 'FORMAL' | 'PRACTICE'
  accepted_at: string
}
export type ResultProps = { submissionId: string; onClose: () => void }
export type TeachingIntegrations = {
  preflight: {
    enqueue: (versionId: string, revision: number) => Promise<Preflight>
    read: (id: string) => Promise<PreflightStatus>
  }
  submissions: { send: (intent: Readonly<SubmissionIntent>) => Promise<SubmissionReceipt> }
  ResultPanel?: ComponentType<ResultProps>
}
const unavailable = (name: string): never => {
  throw new ApiError(503, 'INTEGRATION_UNAVAILABLE', `${name}服务尚未接入。`)
}
// Preflight uses formal HTTP; submission/ResultPanel await their B implementation.
export const teaching: TeachingIntegrations = {
  preflight: {
    enqueue: (id, revision) => api.enqueuePreflight(id, revision),
    read: (id) => api.preflight(id),
  },
  submissions: { send: async () => unavailable('提交') },
}
export function configureTeachingIntegrations(value: TeachingIntegrations) {
  Object.assign(teaching, value)
}
