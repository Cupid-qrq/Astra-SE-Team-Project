import type { ComponentType } from 'react'
import { ApiError } from '../../lib/api/client'

export type Preflight = {
  preflight_id: string
  state: 'QUEUED' | 'RUNNING' | 'PASSED' | 'FAILED'
  content_digest: string
  summary?: string
}
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
    read: (id: string) => Promise<Preflight>
  }
  submissions: { send: (intent: Readonly<SubmissionIntent>) => Promise<SubmissionReceipt> }
  ResultPanel?: ComponentType<ResultProps>
}
const unavailable = (name: string): never => {
  throw new ApiError(503, 'INTEGRATION_UNAVAILABLE', `${name}服务尚未接入。`)
}
// B supplies transport/ResultPanel at composition time. This module never simulates acceptance.
export const teaching: TeachingIntegrations = {
  preflight: { enqueue: async () => unavailable('预检'), read: async () => unavailable('预检') },
  submissions: { send: async () => unavailable('提交') },
}
export function configureTeachingIntegrations(value: TeachingIntegrations) {
  Object.assign(teaching, value)
}
