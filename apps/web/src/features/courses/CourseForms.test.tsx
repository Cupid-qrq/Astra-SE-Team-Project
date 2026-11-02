import { InfiniteQueryObserver, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../../app/runtime'
import { CreateCourseForm } from './CourseForms'
import { courses } from '../../mocks/fixtures'

afterEach(() => vi.restoreAllMocks())
it('建课失败保留标题，成功后才清空', async () => {
  const create = vi
    .spyOn(api, 'createCourse')
    .mockRejectedValueOnce(new Error('保存失败'))
    .mockResolvedValueOnce({ course_id: crypto.randomUUID(), revision: 1 })
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <CreateCourseForm />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('新课程名称'), '程序设计基础')
  await user.click(screen.getByRole('button', { name: '创建课程' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('保存失败')
  expect(screen.getByLabelText('新课程名称')).toHaveValue('程序设计基础')
  await user.click(screen.getByRole('button', { name: '创建课程' }))
  expect(await screen.findByText('课程已创建。')).toBeVisible()
  expect(create).toHaveBeenLastCalledWith({ title: '程序设计基础' }, expect.anything())
})

it('首屏课程读取未结束时建课，仍读取新列表并丢弃迟到的旧结果', async () => {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const oldPage = { items: [courses[0]!], next_cursor: null }
  const created = { ...courses[0]!, course_id: crypto.randomUUID(), title: '并发创建课程' }
  const freshPage = { items: [...oldPage.items, created], next_cursor: null }
  let resolveInitial!: (value: typeof oldPage) => void
  const initial = new Promise<typeof oldPage>((resolve) => {
    resolveInitial = resolve
  })
  const list = vi
    .spyOn(api, 'courses')
    .mockImplementationOnce(() => initial)
    .mockResolvedValue(freshPage)
  vi.spyOn(api, 'createCourse').mockResolvedValue({ course_id: created.course_id, revision: 1 })
  const observer = new InfiniteQueryObserver(cache, {
    queryKey: ['courses'],
    queryFn: () => api.courses(),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
  })
  const unsubscribe = observer.subscribe(() => {})
  try {
    render(
      <QueryClientProvider client={cache}>
        <MemoryRouter>
          <CreateCourseForm />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await waitFor(() => expect(list).toHaveBeenCalledTimes(1))
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('新课程名称'), created.title)
    await user.click(screen.getByRole('button', { name: '创建课程' }))
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
    await act(async () => {
      resolveInitial(oldPage)
      await initial
    })
    await waitFor(() =>
      expect(cache.getQueryData(['courses'])).toMatchObject({ pages: [freshPage] }),
    )
    expect(await screen.findByText('课程已创建。')).toBeVisible()
  } finally {
    resolveInitial(oldPage)
    unsubscribe()
    cache.clear()
  }
})
