import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { api, sessionKey } from '../../app/runtime'
import { AssignmentPage } from './AssignmentPages'
import type { components } from '../../lib/api/schema'

afterEach(() => vi.restoreAllMocks())
it('确认框固定打开时的修订和参数，后台更新不能绕过冲突检查', async () => {
  const value = {
    assignment_id: 'a',
    course_id: 'c',
    title: '已核对作业',
    state: 'OPEN',
    revision: 1,
    items: [],
    ai_policy: 'DISABLED',
    open_at: '2026-01-01T00:00:00.000Z',
    due_at: '2026-10-26T00:00:00.000Z',
    server_time: '2026-10-25T00:00:00.000Z',
    grade_state: 'PROVISIONAL',
    fairness_review: 'NONE',
    fairness_notice: null,
  } as components['schemas']['AssignmentView']
  vi.spyOn(api, 'assignment').mockResolvedValue(value)
  const extend = vi.spyOn(api, 'extendAssignment').mockRejectedValue(new Error('修订冲突'))
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  client.setQueryData(sessionKey, {
    authenticated: true,
    user: { role: 'TEACHER', user_id: 'teacher' },
  })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/assignments/a']}>
        <Routes>
          <Route path="/assignments/:id" element={<AssignmentPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  const user = userEvent.setup()
  await screen.findByRole('heading', { name: '已核对作业' })
  await user.type(screen.getByLabelText('操作理由'), '已经与全班核对延期安排')
  await user.type(screen.getByLabelText('新的截止时间（北京时间）'), '2026-10-28T08:00')
  await user.click(screen.getByRole('button', { name: '统一延期' }))
  act(() =>
    client.setQueryData(['assignment', 'a'], {
      ...value,
      revision: 2,
      title: '别人刚刚修改的作业',
    }),
  )
  await user.click(screen.getByRole('button', { name: '确认调整' }))
  await waitFor(() => expect(extend).toHaveBeenCalled())
  expect(extend.mock.calls[0][1].expected_revision).toBe(1)
})
