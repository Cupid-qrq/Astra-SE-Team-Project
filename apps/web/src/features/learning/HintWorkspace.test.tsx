import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api } from '../../app/runtime'
import { ApiError } from '../../lib/api/client'
import { HintWorkspace } from './HintWorkspace'

const submission = '10000000-0000-4000-8000-000000000001'
const hint = '10000000-0000-4000-8000-000000000002'
const view = {
  hint_id: hint,
  submission_id: submission,
  status: 'READY' as const,
  reason_code: null,
  model_version: 'test-model',
  template_version_id: hint,
  created_at: '2026-01-01T00:00:00.000Z',
  fallback_feedback: null,
  sections: {
    error_category: '运算',
    location_clues: '表达式',
    checks: '检查符号',
    learning_advice: '手算验证',
  },
}
function mount(ownerId = 'student-a') {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
        })
      }
    >
      <HintWorkspace ownerId={ownerId} submissionId={submission} />
    </QueryClientProvider>,
  )
}
beforeEach(() => {
  localStorage.clear()
  vi.spyOn(api, 'hintHistory').mockResolvedValue({ items: [], next_cursor: null })
})
afterEach(() => vi.restoreAllMocks())
it('需主动同意外发；连接中断后重用请求键，重新获取本人历史；就绪后可评价', async () => {
  const create = vi
    .spyOn(api, 'createHint')
    .mockRejectedValueOnce(new ApiError(0, 'NETWORK_ERROR', '连接中断'))
    .mockResolvedValue({ hint_id: hint, status: 'PENDING' })
  vi.spyOn(api, 'hint').mockResolvedValue(view)
  const rate = vi.spyOn(api, 'rateHint').mockResolvedValue({ rating: 'USEFUL' })
  const part = mount()
  expect(screen.getByRole('button', { name: '请求提示' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('想问的问题（可选）'), {
    target: { value: '应该检查什么？' },
  })
  await userEvent.click(screen.getByRole('checkbox'))
  await userEvent.click(screen.getByRole('button', { name: '请求提示' }))
  await userEvent.click(await screen.findByRole('button', { name: '核对上次请求' }))
  expect(create.mock.calls[0][0]).toEqual(create.mock.calls[1][0])
  const result = await screen.findByRole('region', { name: '提示详情' })
  expect(within(result).getByText('检查符号')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '保存评价' }))
  expect(rate).toHaveBeenCalledWith(hint, { rating: 'USEFUL' })
  expect(api.hintHistory).toHaveBeenCalled()
  expect(Object.values(localStorage).join('')).not.toMatch(/检查符号|应该检查什么/)
  part.unmount()
  mount('student-b')
  expect(screen.queryByRole('button', { name: hint })).toBeNull()
})
it('策略拒绝时不展示旧段落或评价入口', async () => {
  vi.spyOn(api, 'hint').mockResolvedValue({
    ...view,
    status: 'BLOCKED',
    sections: null,
    reason_code: 'FAMILY_POLICY',
  })
  mount()
  fireEvent.change(screen.getByLabelText('提示编号'), { target: { value: hint } })
  await userEvent.click(screen.getByRole('button', { name: '查阅提示' }))
  expect(await screen.findByText(/FAMILY_POLICY/)).toBeVisible()
  expect(screen.queryByRole('button', { name: '保存评价' })).toBeNull()
})

it('分页历史只显示服务器授权的编号，打开时重新获取正文', async () => {
  vi.mocked(api.hintHistory)
    .mockResolvedValueOnce({
      items: [{ hint_id: hint, created_at: view.created_at }],
      next_cursor: 'next',
    })
    .mockResolvedValue({
      items: [{ hint_id: submission, created_at: view.created_at }],
      next_cursor: null,
    })
  const read = vi.spyOn(api, 'hint').mockResolvedValue(view)
  mount()
  await userEvent.click(await screen.findByRole('button', { name: '加载更多提示' }))
  expect(api.hintHistory).toHaveBeenLastCalledWith('next')
  await userEvent.click(await screen.findByRole('button', { name: hint }))
  expect(read).toHaveBeenCalledWith(hint)
})

it('后台权限复核隐藏旧内容，但保留尚未提交的评价', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  let resolveRead: (value: typeof view) => void = () => {}
  const read = vi
    .spyOn(api, 'hint')
    .mockResolvedValueOnce(view)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRead = resolve
        }),
    )
  render(
    <QueryClientProvider client={client}>
      <HintWorkspace ownerId="student-a" />
    </QueryClientProvider>,
  )
  fireEvent.change(screen.getByLabelText('提示编号'), { target: { value: hint } })
  await userEvent.click(screen.getByRole('button', { name: '查阅提示' }))
  fireEvent.change(await screen.findByLabelText('评价说明（可选）'), {
    target: { value: '希望补充边界说明' },
  })
  await act(async () => {
    void client.invalidateQueries({ queryKey: ['studentHint', hint] })
  })
  expect(read).toHaveBeenCalledTimes(2)
  await waitFor(() => expect(screen.queryByRole('region', { name: '提示详情' })).toBeNull())
  await act(async () => {
    resolveRead(view)
  })
  expect(await screen.findByLabelText('评价说明（可选）')).toHaveValue('希望补充边界说明')
})

it('从本人错题填入真实示例时清除外发同意，最近提示仅填入编号', async () => {
  vi.mocked(api.hintHistory).mockResolvedValue({
    items: [{ hint_id: hint, created_at: view.created_at }],
    next_cursor: null,
  })
  const create = vi.spyOn(api, 'createHint')
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <HintWorkspace
        ownerId="student-a"
        examples={[{ submission_id: submission, title: '演示求和', verdict: 'WA' }]}
      />
    </QueryClientProvider>,
  )
  await userEvent.click(screen.getByRole('checkbox'))
  await userEvent.selectOptions(screen.getByLabelText('从本人错题选择示例'), submission)
  expect(screen.getByLabelText('来源提交编号')).toHaveValue(submission)
  expect(screen.getByRole('checkbox')).not.toBeChecked()
  expect(screen.getByRole('button', { name: '请求提示' })).toHaveAttribute(
    'title',
    '请先勾选本次外发同意。',
  )
  await userEvent.click(await screen.findByRole('button', { name: '填入最近提示编号' }))
  expect(screen.getByLabelText('提示编号')).toHaveValue(hint)
  expect(create).not.toHaveBeenCalled()
})

it('历史重新核验失败后隐藏最近编号快捷入口', async () => {
  vi.mocked(api.hintHistory).mockResolvedValue({
    items: [{ hint_id: hint, created_at: view.created_at }],
    next_cursor: null,
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <HintWorkspace ownerId="student-a" />
    </QueryClientProvider>,
  )
  await screen.findByRole('button', { name: '填入最近提示编号' })
  vi.mocked(api.hintHistory).mockRejectedValue(new ApiError(403, 'FORBIDDEN', '无权读取'))
  await act(async () => {
    await client.invalidateQueries({ queryKey: ['hintHistory'] })
  })
  await waitFor(() => expect(screen.queryByRole('button', { name: '填入最近提示编号' })).toBeNull())
})

it('错题为空时可从最近已授权提示填入来源且不会发送新请求', async () => {
  vi.mocked(api.hintHistory).mockResolvedValue({
    items: [{ hint_id: hint, created_at: view.created_at }],
    next_cursor: null,
  })
  vi.spyOn(api, 'hint').mockResolvedValue(view)
  const create = vi.spyOn(api, 'createHint')
  mount()
  await userEvent.click(screen.getByRole('checkbox'))
  await userEvent.click(await screen.findByRole('button', { name: '填入最近提示的来源提交' }))
  await waitFor(() => expect(screen.getByRole('checkbox')).not.toBeChecked())
  expect(screen.getByLabelText('来源提交编号')).toHaveValue(submission)
  expect(create).not.toHaveBeenCalled()
})
