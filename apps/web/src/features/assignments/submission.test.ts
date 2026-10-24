import { expect, it, vi } from 'vitest'
import { createSubmissionAttempt, restoreSubmissionAttempt } from './submission'
import { ApiError } from '../../lib/api/client'

it('未知受理和限流重试保持同一键、摘要与原代码，修改代码不能混入重放', async () => {
  const send = vi
    .fn()
    .mockRejectedValueOnce(new ApiError(0, 'NETWORK_ERROR', '网络断开'))
    .mockResolvedValueOnce({
      submission_id: 'accepted',
      mode: 'FORMAL',
      accepted_at: '2026-10-25T00:00:00.000Z',
    })
  const attempt = await createSubmissionAttempt({
    assignment_id: 'a',
    problem_id: 'p',
    language_key: 'python3',
    code: 'print(1)',
    intent: 'FORMAL',
  })
  await expect(attempt.send(send)).rejects.toThrow('网络断开')
  await attempt.send(send)
  expect(send.mock.calls[0][0]).toEqual(send.mock.calls[1][0])
  expect(send.mock.calls[0][0].code).toBe('print(1)')
  expect(send.mock.calls[0][0].code_sha256).toMatch(/^[a-f0-9]{64}$/)
  expect(Object.isFrozen(attempt.intent)).toBe(true)
})
it('空白和UTF-8超限源码不得创建提交意图', async () => {
  for (const code of ['   \n', '汉'.repeat(22000)])
    await expect(
      createSubmissionAttempt({
        assignment_id: 'a',
        problem_id: 'p',
        language_key: 'python3',
        code,
        intent: 'FORMAL',
      }),
    ).rejects.toThrow()
})

it('本地待重放快照必须属于当前作业题目和语言', async () => {
  const attempt = await createSubmissionAttempt({
    assignment_id: 'a',
    problem_id: 'p',
    language_key: 'python3',
    code: 'print(1)',
    intent: 'FORMAL',
  })
  await expect(
    restoreSubmissionAttempt(attempt.intent, {
      assignmentId: 'other',
      problemId: 'p',
      language: 'python3',
    }),
  ).rejects.toThrow('不属于')
})

it('未知受理后明确意图拒绝解除快照，认证失效和限流仍保留原键', async () => {
  const attempt = await createSubmissionAttempt({
    assignment_id: 'a',
    problem_id: 'p',
    language_key: 'python3',
    code: 'print(1)',
    intent: 'FORMAL',
  })
  const errors = [
    new ApiError(0, 'NETWORK_ERROR', '断网'),
    new ApiError(401, 'UNAUTHENTICATED', '失效'),
    new ApiError(429, 'STUDENT_INTERVAL', '稍后重试'),
  ]
  for (const error of errors) {
    await expect(
      attempt.send(async () => {
        throw error
      }),
    ).rejects.toThrow()
    expect(attempt.uncertain).toBe(true)
  }
  await expect(
    attempt.send(async () => {
      throw new ApiError(409, 'SUBMISSION_INTENT_MISMATCH', '正式提交已截止')
    }),
  ).rejects.toThrow()
  expect(attempt.uncertain).toBe(false)
})
