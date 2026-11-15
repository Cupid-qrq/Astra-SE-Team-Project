import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../../app/runtime'
import { courses, user } from '../../mocks/fixtures'
import { communityApi } from './communityApi'
import { LeaderboardPage } from './LeaderboardPage'
import { DiscussionPage } from './DiscussionPage'

afterEach(() => vi.restoreAllMocks())
function mount(page: React.ReactNode, path: string, entry: string) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path={path} element={page} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
it('保留服务端并列名次与零分，并明确榜单范围', async () => {
  vi.spyOn(api, 'session').mockResolvedValue({
    authenticated: true,
    user,
    csrf_token: 'test',
    server_time: '2026-11-05T00:00:00Z',
  })
  vi.spyOn(api, 'course').mockResolvedValue(courses[0])
  vi.spyOn(communityApi, 'leaderboard').mockResolvedValue({
    course_id: 'course-a',
    kind: 'progress',
    updated_at: '2026-11-05T00:00:00Z',
    included_assignments: 2,
    show_name: false,
    items: [
      { entry_id: '1', rank: 1, display_name: '匿名同学一', value: 0, is_me: true },
      { entry_id: '2', rank: 1, display_name: '匿名同学二', value: 0, is_me: false },
    ],
    next_cursor: null,
  })
  mount(<LeaderboardPage />, '/courses/:id/leaderboard', '/courses/course-a/leaderboard')
  expect(await screen.findByText('匿名同学一')).toBeVisible()
  expect(screen.getAllByRole('cell', { name: '1' })).toHaveLength(2)
  expect(screen.getAllByRole('cell', { name: '0' })).toHaveLength(2)
  expect(screen.getByText(/不计练习/)).toBeVisible()
})
it('锁定讨论禁止回复；普通读者不显示管理操作', async () => {
  vi.spyOn(api, 'course').mockResolvedValue(courses[0])
  vi.spyOn(communityApi, 'discussion').mockResolvedValue({
    thread: {
      thread_id: 't',
      course_id: 'course-a',
      problem_id: 'p',
      version_id: 'v',
      title: '边界问题',
      body: '如何理解边界？',
      author_name: '同学',
      is_mine: false,
      can_moderate: false,
      resolved: false,
      locked: true,
      pinned: false,
      hidden: false,
      revision: 1,
      reply_count: 0,
      created_at: '2026-11-05T00:00:00Z',
      updated_at: '2026-11-05T00:00:00Z',
    },
    replies: [],
    next_cursor: null,
  })
  mount(<DiscussionPage />, '/discussions/:id', '/discussions/t')
  expect(await screen.findByText('边界问题')).toBeVisible()
  expect(screen.queryByRole('button', { name: '发布回复' })).toBeNull()
  expect(screen.queryByText('管理理由')).toBeNull()
  expect(screen.getByText(/讨论已锁定/)).toBeVisible()
})
it('拒绝空白回复，发布后重新读取讨论', async () => {
  vi.spyOn(api, 'course').mockResolvedValue(courses[0])
  vi.spyOn(communityApi, 'discussion').mockResolvedValue({
    thread: {
      thread_id: 't',
      course_id: 'course-a',
      problem_id: 'p',
      version_id: 'v',
      title: '边界问题',
      body: '如何理解边界？',
      author_name: '同学',
      is_mine: false,
      can_moderate: false,
      resolved: false,
      locked: false,
      pinned: false,
      hidden: false,
      revision: 1,
      reply_count: 0,
      created_at: '2026-11-05T00:00:00Z',
      updated_at: '2026-11-05T00:00:00Z',
    },
    replies: [],
    next_cursor: null,
  })
  mount(<DiscussionPage />, '/discussions/:id', '/discussions/t')
  let finishReply: () => void = () => {}
  const send = vi.spyOn(communityApi, 'reply').mockImplementation(
    () =>
      new Promise((resolve) => {
        finishReply = () =>
          resolve({
            reply_id: 'r',
            thread_id: 't',
            body: '先检查边界',
            author_name: '同学',
            is_mine: true,
            hidden: false,
            revision: 1,
            created_at: '2026-11-05T00:00:00Z',
          })
      }),
  )
  const input = await screen.findByLabelText('回复正文')
  await userEvent.type(input, '   ')
  expect(screen.getByRole('button', { name: '发布回复' })).toBeDisabled()
  await userEvent.clear(input)
  await userEvent.type(input, '先检查边界')
  await userEvent.click(screen.getByRole('button', { name: '发布回复' }))
  await waitFor(() => expect(send).toHaveBeenCalledWith('t', '先检查边界'))
  expect(input).toBeDisabled()
  finishReply()
  await waitFor(() => expect(communityApi.discussion).toHaveBeenCalledTimes(2))
  expect(input).toHaveValue('')
})
