import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { ResultSummary } from './SubmissionResult'

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
