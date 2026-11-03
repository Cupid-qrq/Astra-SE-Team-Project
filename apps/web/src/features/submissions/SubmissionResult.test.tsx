import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { api } from '../../app/runtime'
import { ResultSummary, SubmissionContent, type Submission } from './SubmissionResult'

afterEach(() => vi.restoreAllMocks())

it('平台故障与未知资源有明确说明，显示正式性与已执行点', () => {
  render(
    <ResultSummary
      value={{
        state: 'FINISHED',
        verdict: 'SE',
        mode: 'FORMAL',
        generation: 2,
        time_ms: null,
        memory_bytes: null,
        case_results: [
          { order: 1, verdict: 'SE', cpu_ms: null, memory_bytes: null },
          { order: 2, verdict: 'SKIPPED', cpu_ms: null, memory_bytes: null },
        ],
      }}
    />,
  )
  expect(screen.getByRole('heading', { name: '平台故障' })).toBeInTheDocument()
  expect(screen.getByText('正式提交')).toBeInTheDocument()
  expect(screen.getByText(/第 2 轮/)).toBeInTheDocument()
  expect(screen.getAllByText(/未知/).length).toBeGreaterThan(0)
  expect(screen.getByText('未执行')).toBeInTheDocument()
})

it('处理中保留状态文字且不提前展示判定', () => {
  render(
    <ResultSummary
      value={{
        state: 'RETRY_WAIT',
        verdict: null,
        mode: 'PRACTICE',
        generation: 2,
        time_ms: null,
        memory_bytes: null,
        case_results: [],
      }}
    />,
  )
  expect(screen.getByText('等待重试')).toBeInTheDocument()
  expect(screen.getByText('练习提交')).toBeInTheDocument()
  expect(screen.queryByText('通过')).not.toBeInTheDocument()
})

it('结果与帮助两次GET之间换轮时丢弃错配帮助并重新读取一致结果', async () => {
  const old: Submission = {
    submission_id: 'submission',
    assignment_id: 'assignment',
    problem_id: 'problem',
    original_version_id: 'version-1',
    effective_version_id: 'version-1',
    result_basis_id: 'basis-1',
    code: '# synthetic',
    language_key: 'python3',
    accepted_at: '2026-11-03T08:00:00Z',
    reason_code: null,
    revision: 1,
    state: 'FINISHED',
    verdict: 'WA',
    mode: 'FORMAL',
    generation: 1,
    time_ms: null,
    memory_bytes: null,
    case_results: [],
    attempt_id: 'attempt-1',
    feedback_version_id: 'feedback-1',
  }
  vi.spyOn(api, 'submission')
    .mockResolvedValueOnce(old)
    .mockResolvedValue({
      ...old,
      verdict: 'RE',
      generation: 2,
      attempt_id: 'attempt-2',
      feedback_version_id: 'feedback-2',
    })
  vi.spyOn(api, 'submissionFeedback').mockResolvedValue({
    feedback_version_id: 'feedback-2',
    title: '新轮运行错误帮助',
    explanation: '检查数组边界。',
    checklist: [],
  })
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <SubmissionContent submissionId="submission" />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  await waitFor(() => expect(screen.getByText('第 2 轮')).toBeVisible())
  expect(await screen.findByRole('heading', { name: '新轮运行错误帮助' })).toBeVisible()
  expect(screen.queryByText('第 1 轮')).not.toBeInTheDocument()
})
