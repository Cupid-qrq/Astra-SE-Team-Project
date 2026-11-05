import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api } from '../../app/runtime'
import { TemplateEditor } from './TemplateEditor'

const initial = {
  template_id: 'template-a',
  body: '阅读 {question}',
  allowed_placeholders: ['question'] as 'question'[],
  schema_version: '1',
  revision: 3,
  course_id: 'course-a',
  scope: 'COURSE' as const,
  course_status: 'ACTIVE' as const,
  published_version_id: null,
  published_version_no: null,
}
function mount(value = initial, owner = 'teacher-a') {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <TemplateEditor
        ownerId={owner}
        initial={value}
        courseId="course-a"
        onCreated={vi.fn()}
        onReload={vi.fn()}
      />
    </QueryClientProvider>,
  )
}
beforeEach(() => sessionStorage.clear())
afterEach(() => vi.restoreAllMocks())
it('恢复按账号隔离，冲突重试仍绑定编辑时的修订', async () => {
  const save = vi.spyOn(api, 'saveTemplate').mockRejectedValue(new Error('修订冲突'))
  const view = mount()
  fireEvent.change(screen.getByLabelText('给 AI 的指导要求'), {
    target: { value: '根据 {question} 思考' },
  })
  view.unmount()
  const other = mount(initial, 'teacher-b')
  expect(screen.queryByText('恢复本地编辑')).toBeNull()
  other.unmount()
  mount({ ...initial, revision: 7 })
  await userEvent.click(screen.getByText('恢复本地编辑'))
  await userEvent.click(screen.getByText('保存草稿'))
  expect(await screen.findByRole('alert')).toHaveTextContent('修订冲突')
  expect(save).toHaveBeenCalledWith('template-a', {
    expected_revision: 3,
    body: '根据 {question} 思考',
    allowed_placeholders: ['question'],
    schema_version: '1',
  })
})
it('预览使用示例并拦截未勾选的占位符与超字节正文', () => {
  mount()
  expect(screen.getByRole('region', { name: '示例预览' })).toHaveTextContent('我应该先检查哪个运算')
  for (const body of ['{student_code}', '{secret}', '{question', '题'.repeat(2731)]) {
    fireEvent.change(screen.getByLabelText('给 AI 的指导要求'), { target: { value: body } })
    expect(screen.getByRole('button', { name: '保存草稿' })).toBeDisabled()
  }
})
