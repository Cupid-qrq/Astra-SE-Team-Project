import { ApiError } from '../../lib/api/client'
import type { SubmissionIntent, SubmissionReceipt } from '../integrations/teaching'
type Input = Omit<SubmissionIntent, 'idempotency_key' | 'code_sha256'>
export type SubmissionAttempt = {
  intent: Readonly<SubmissionIntent>
  uncertain: boolean
  send: (
    transport: (value: Readonly<SubmissionIntent>) => Promise<SubmissionReceipt>,
  ) => Promise<SubmissionReceipt>
}
async function codeDigest(code: string) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(code)))]
    .map((n) => n.toString(16).padStart(2, '0'))
    .join('')
}
function attemptFrom(intent: SubmissionIntent, uncertain: boolean): SubmissionAttempt {
  const attempt: SubmissionAttempt = {
    intent: Object.freeze({ ...intent }),
    uncertain,
    async send(transport) {
      try {
        const result = await transport(attempt.intent)
        attempt.uncertain = false
        return result
      } catch (error) {
        // Only this business refusal proves no accepted receipt exists: the
        // server must replay an existing receipt BEFORE checking current cutoff.
        if (
          error instanceof ApiError &&
          error.status === 409 &&
          error.code === 'SUBMISSION_INTENT_MISMATCH'
        )
          attempt.uncertain = false
        else if (
          !(error instanceof ApiError) ||
          (error.code !== 'INTEGRATION_UNAVAILABLE' &&
            (error.status === 0 || error.status === 429 || error.status >= 500))
        )
          attempt.uncertain = true
        throw error
      }
    },
  }
  return attempt
}
export async function createSubmissionAttempt(input: Input): Promise<SubmissionAttempt> {
  if (!input.code.trim()) throw new Error('代码不能为空白。')
  if (new TextEncoder().encode(input.code).byteLength > 65536)
    throw new Error('源码超过 UTF-8 64 KiB 上限。')
  return attemptFrom(
    { ...input, code_sha256: await codeDigest(input.code), idempotency_key: crypto.randomUUID() },
    false,
  )
}
export async function restoreSubmissionAttempt(
  intent: SubmissionIntent,
  context: { assignmentId: string; problemId: string; language: string },
): Promise<SubmissionAttempt> {
  if (
    intent.assignment_id !== context.assignmentId ||
    intent.problem_id !== context.problemId ||
    intent.language_key !== context.language
  )
    throw new Error('本机提交快照不属于当前作业、题目或语言，请保留代码并联系教师。')
  if ((await codeDigest(intent.code)) !== intent.code_sha256)
    throw new Error('本机提交快照摘要不一致，请保留代码并联系教师。')
  return attemptFrom(intent, true)
}
