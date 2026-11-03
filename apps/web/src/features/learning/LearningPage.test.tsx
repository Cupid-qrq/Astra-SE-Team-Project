import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Link } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { api, sessionKey } from '../../app/runtime'
import LearningPage from './LearningPage'

afterEach(() => vi.restoreAllMocks())
it('同页导航到另一来源提交时更新表单并要求重新同意', async () => {
  vi.spyOn(api, 'reviewItems').mockResolvedValue({ items: [], next_cursor: null })
  vi.spyOn(api, 'recommendations').mockResolvedValue({ items: [] })
  vi.spyOn(api, 'hintHistory').mockResolvedValue({ items: [], next_cursor: null })
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } })
  client.setQueryData(sessionKey, {
    authenticated: true,
    user: { user_id: 'student-a', role: 'STUDENT' },
  })
  const first = '10000000-0000-4000-8000-000000000001'
  const second = '10000000-0000-4000-8000-000000000002'
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/learning?submission_id=' + first]}>
        <Link to={'/learning?submission_id=' + second}>另一提交</Link>
        <LearningPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  expect(screen.getByLabelText('来源提交编号')).toHaveValue(first)
  await userEvent.click(screen.getByRole('checkbox'))
  await userEvent.click(screen.getByRole('link', { name: '另一提交' }))
  expect(screen.getByLabelText('来源提交编号')).toHaveValue(second)
  expect(screen.getByRole('checkbox')).not.toBeChecked()
})

it('重新核验错题失败后隐藏旧示例选项', async () => {
  const id = '10000000-0000-4000-8000-000000000001'
  const review = vi
    .spyOn(api, 'reviewItems')
    .mockResolvedValue({
      items: [
        {
          submission_id: id,
          assignment_id: id,
          problem_id: id,
          title: '旧授权题目',
          verdict: 'WA',
          context: 'FORMAL',
          accepted_at: '2026-01-01T00:00:00Z',
        },
      ],
      next_cursor: null,
    })
  vi.spyOn(api, 'recommendations').mockResolvedValue({ items: [] })
  vi.spyOn(api, 'hintHistory').mockResolvedValue({ items: [], next_cursor: null })
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  client.setQueryData(sessionKey, {
    authenticated: true,
    user: { user_id: 'student-a', role: 'STUDENT' },
  })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <LearningPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  await screen.findByLabelText('从本人错题选择示例')
  review.mockRejectedValue(new Error('无权读取'))
  await act(async () => {
    await client.invalidateQueries({ queryKey: ['reviewItems'] })
  })
  await waitFor(() => expect(screen.queryByLabelText('从本人错题选择示例')).toBeNull())
})
