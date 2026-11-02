import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api } from '../../app/runtime'
import { FeedbackEditor } from './FeedbackEditor'
import { readHelpDraft, writeHelpDraft } from './feedbackDrafts'
import type { components } from '../../lib/api/schema'

const initial: components['schemas']['FeedbackDraftView'] = {
  catalog_id: 'catalog-a',
  revision: 1,
  title: '已有标题',
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
beforeEach(() => {
  sessionStorage.clear()
  vi.spyOn(api, 'feedbackHistory').mockResolvedValue({ items: [], next_cursor: null })
})
afterEach(() => vi.restoreAllMocks())

function mount(value = initial) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const props = { initial: value, ownerId: 'teacher-a', onReload: vi.fn() }
  const view = render(
    <QueryClientProvider client={client}>
      <FeedbackEditor {...props} />
    </QueryClientProvider>,
  )
  return {
    ...view,
    changeInitial: (next: typeof initial) =>
      view.rerender(
        <QueryClientProvider client={client}>
          <FeedbackEditor {...props} initial={next} />
        </QueryClientProvider>,
      ),
  }
}

it('保存冲突保留当前编辑与原修订，服务器刷新不会偷换修订', async () => {
  const save = vi.spyOn(api, 'saveFeedbackDraft').mockRejectedValue(new Error('修订冲突'))
  const view = mount()
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('帮助标题'), '本地内容')
  view.changeInitial({ ...initial, revision: 9, title: '其他人更新' })
  await user.click(screen.getByRole('button', { name: '保存草稿' }))
  await screen.findByText(/修订冲突/)
  expect(screen.getByLabelText('帮助标题')).toHaveValue('已有标题本地内容')
  expect(save).toHaveBeenCalledWith('catalog-a', {
    title: '已有标题本地内容',
    explanation: '检查边界。',
    checklist: [],
    expected_revision: 1,
  })
  expect(readHelpDraft('teacher-a', 'catalog-a')?.fields.title).toBe('已有标题本地内容')
  expect(readHelpDraft('teacher-b', 'catalog-a')).toBeNull()
})

it('发布确认冻结核对过的修订和理由', async () => {
  const publish = vi.spyOn(api, 'publishFeedback').mockRejectedValue(new Error('修订冲突'))
  const view = mount()
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('发布理由'), '已经核对本课教学目标与检查方向')
  await user.click(screen.getByRole('button', { name: '发布新版本' }))
  view.changeInitial({ ...initial, revision: 7 })
  await user.click(screen.getByRole('button', { name: '确认发布' }))
  await screen.findByText(/修订冲突/)
  expect(publish).toHaveBeenCalledWith('catalog-a', {
    expected_revision: 1,
    reason: '已经核对本课教学目标与检查方向',
  })
})

it('恢复本地编辑仍用原修订，不能覆盖服务器新内容', async () => {
  writeHelpDraft('teacher-a', 'catalog-a', {
    revision: 2,
    fields: { title: '离线编辑', explanation: '未保存说明', checklistText: '检查输入' },
  })
  const save = vi.spyOn(api, 'saveFeedbackDraft').mockRejectedValue(new Error('修订冲突'))
  mount({ ...initial, revision: 8 })
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '恢复本地编辑' }))
  await user.click(screen.getByRole('button', { name: '保存草稿' }))
  await screen.findByText(/修订冲突/)
  expect(save.mock.calls[0][1].expected_revision).toBe(2)
  expect(screen.getByLabelText('帮助标题')).toHaveValue('离线编辑')
})

it('撤销全部本地修改后不留下过时恢复内容', async () => {
  const view = mount()
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('帮助标题'), 'X')
  await waitFor(() => expect(readHelpDraft('teacher-a', 'catalog-a')).not.toBeNull())
  await user.type(screen.getByLabelText('帮助标题'), '{Backspace}')
  view.unmount()
  expect(readHelpDraft('teacher-a', 'catalog-a')).toBeNull()
})

it('开始新的编辑后不会再显示会覆盖当前内容的旧恢复按钮', async () => {
  writeHelpDraft('teacher-a', 'catalog-a', {
    revision: 1,
    fields: { title: '旧恢复内容', explanation: '旧内容', checklistText: '' },
  })
  mount()
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('帮助标题'), '新的编辑')
  expect(screen.queryByRole('button', { name: '恢复本地编辑' })).not.toBeInTheDocument()
  expect(readHelpDraft('teacher-a', 'catalog-a')?.fields.title).toBe('已有标题新的编辑')
})
