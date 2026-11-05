import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../../app/runtime'
import { courses, user } from '../../mocks/fixtures'
import { TemplatesPage } from './TemplatePages'

afterEach(() => vi.restoreAllMocks())
function mount(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  vi.spyOn(api, 'session').mockResolvedValue({
    authenticated: true,
    user: { ...user, role: 'TEACHER' },
    csrf_token: 'test',
    server_time: '2026-11-05T00:00:00Z',
  })
  vi.spyOn(api, 'templates').mockResolvedValue({
    items: [
      { template_id: 'template-a', course_id: 'course-a', scope: 'COURSE', revision: 2 },
      { template_id: 'template-b', course_id: 'course-b', scope: 'COURSE', revision: 2 },
    ],
    next_cursor: null,
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/teacher/hint-templates']}>
        <TemplatesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
it('辅导目录以课程名称区分要求并保留各自课程链接', async () => {
  vi.spyOn(api, 'courses').mockResolvedValue({
    items: [
      { ...courses[0], course_id: 'course-a', title: '程序设计实践 · 秋季学期' },
      { ...courses[0], course_id: 'course-b', title: '数据结构入门 · 秋季学期' },
    ],
    next_cursor: null,
  })
  mount()
  const first = await screen.findByRole('link', { name: '程序设计实践 · 秋季学期' })
  expect(first).toHaveAttribute('href', '/teacher/hint-templates/template-a?course_id=course-a')
  expect(screen.getByRole('link', { name: '数据结构入门 · 秋季学期' })).toHaveAttribute(
    'href',
    '/teacher/hint-templates/template-b?course_id=course-b',
  )
  expect(screen.queryByText('查看课程辅导要求')).toBeNull()
})
it('课程名在后续页时按分页读取，不为每条模板单独请求', async () => {
  const calls = vi.spyOn(api, 'courses').mockImplementation(async (cursor) =>
    cursor
      ? {
          items: [{ ...courses[0], course_id: 'course-b', title: '数据结构入门 · 秋季学期' }],
          next_cursor: null,
        }
      : {
          items: [{ ...courses[0], course_id: 'course-a', title: '程序设计实践 · 秋季学期' }],
          next_cursor: 'next-courses',
        },
  )
  mount()
  expect(await screen.findByRole('link', { name: '数据结构入门 · 秋季学期' })).toBeVisible()
  expect(calls).toHaveBeenCalledTimes(2)
  expect(calls).toHaveBeenNthCalledWith(1, undefined)
  expect(calls).toHaveBeenNthCalledWith(2, 'next-courses')
})

it('复用课程缓存时等后台刷新完成后继续加载缺失名称', async () => {
  const firstPage = {
    items: [{ ...courses[0], course_id: 'course-a', title: '程序设计实践 · 秋季学期' }],
    next_cursor: 'next-courses',
  }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(['courses'], { pages: [firstPage], pageParams: [undefined] })
  let resolveFirst!: (value: Awaited<ReturnType<typeof api.courses>>) => void
  const first = new Promise<Awaited<ReturnType<typeof api.courses>>>((resolve) => {
    resolveFirst = resolve
  })
  const calls = vi.spyOn(api, 'courses').mockImplementation(async (cursor) =>
    cursor
      ? {
          items: [{ ...courses[0], course_id: 'course-b', title: '数据结构入门 · 秋季学期' }],
          next_cursor: null,
        }
      : first,
  )
  mount(client)
  await screen.findByRole('link', { name: '程序设计实践 · 秋季学期' })
  await waitFor(() => expect(calls).toHaveBeenCalledWith(undefined))
  await act(async () => resolveFirst(firstPage))
  expect(await screen.findByRole('link', { name: '数据结构入门 · 秋季学期' })).toBeVisible()
  expect(calls).toHaveBeenCalledWith('next-courses')
})
