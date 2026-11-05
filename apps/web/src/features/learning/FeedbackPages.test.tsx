import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api, sessionKey } from '../../app/runtime'
import { FeedbackDetailPage } from './FeedbackPages'
import type { components } from '../../lib/api/schema'

beforeEach(() => {
  sessionStorage.clear()
  vi.spyOn(api, 'feedbackHistory').mockResolvedValue({ items: [], next_cursor: null })
})
afterEach(() => vi.restoreAllMocks())

function mount() {
  const draft: components['schemas']['FeedbackDraftView'] = {
    catalog_id: 'catalog-a',
    revision: 1,
    title: '服务器原始标题',
    explanation: '检查边界。',
    checklist: [],
    scope: 'COURSE',
    course_id: 'course-a',
    verdict: 'WA',
    language_key: 'ALL',
    active_version_id: null,
    active_version_no: null,
    course_status: 'ACTIVE',
  }
  vi.spyOn(api, 'feedbackDraft').mockResolvedValue(draft)
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  client.setQueryData(sessionKey, {
    authenticated: true,
    user: { role: 'TEACHER', user_id: 'teacher-a' },
  })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/teacher/feedback/catalog-a']}>
        <Routes>
          <Route path="/teacher/feedback/:id" element={<FeedbackDetailPage />} />
          <Route
            path="/teacher/feedback"
            element={<Link to="/teacher/feedback/catalog-a">重新进入帮助</Link>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

it('保存后立即离开再进入仍展示已保存的正文和修订', async () => {
  const save = vi.spyOn(api, 'saveFeedbackDraft').mockResolvedValue({ revision: 2 })
  mount()
  const user = userEvent.setup()
  await screen.findByDisplayValue('服务器原始标题')
  await user.clear(screen.getByLabelText('帮助标题'))
  await user.type(screen.getByLabelText('帮助标题'), '已经保存的新标题')
  await user.click(screen.getByRole('button', { name: '保存草稿' }))
  await screen.findByText('草稿已保存，尚未发布。')
  await user.click(screen.getByRole('link', { name: '← 返回帮助目录' }))
  await user.click(screen.getByRole('link', { name: '重新进入帮助' }))
  expect(await screen.findByLabelText('帮助标题')).toHaveValue('已经保存的新标题')
  expect(screen.getByText(/草稿版本 2/)).toBeInTheDocument()
  expect(save).toHaveBeenCalledTimes(1)
})

it('发布后立即重进显示生效版本及递增修订', async () => {
  vi.spyOn(api, 'publishFeedback').mockResolvedValue({
    version_id: 'published-a',
    checksum: 'a'.repeat(64),
  })
  mount()
  const user = userEvent.setup()
  await screen.findByDisplayValue('服务器原始标题')
  await user.type(screen.getByLabelText('发布理由'), '已经核对本课教学目标与检查方向')
  await user.click(screen.getByRole('button', { name: '发布新版本' }))
  await user.click(screen.getByRole('button', { name: '确认发布' }))
  await screen.findByText('新版本已生效，历史版本保持不变。')
  await user.click(screen.getByRole('link', { name: '← 返回帮助目录' }))
  await user.click(screen.getByRole('link', { name: '重新进入帮助' }))
  expect(await screen.findByText('生效版本：1')).toBeVisible()
  expect(screen.getByText(/草稿版本 2/)).toBeInTheDocument()
})
