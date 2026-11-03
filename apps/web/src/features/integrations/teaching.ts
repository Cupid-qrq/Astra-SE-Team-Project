import type { ComponentType } from 'react'
import { SubmissionResult } from '../submissions/SubmissionResult'
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
export const teaching: TeachingIntegrations = {
  preflight: {
    enqueue: (id, revision) => api.enqueuePreflight(id, revision),
    read: (id) => api.preflight(id),
  },
  submissions: {
    send: ({ idempotency_key, intent, assignment_id, problem_id, language_key, code }) =>
      api.sendSubmission(
        { assignment_id, problem_id, language_key, code },
        idempotency_key,
        intent,
      ),
  },
  ResultPanel: SubmissionResult,
}
export function configureTeachingIntegrations(value: TeachingIntegrations) {
  Object.assign(teaching, value)
}
