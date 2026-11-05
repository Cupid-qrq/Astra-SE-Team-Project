import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../../app/runtime'
import { assignments, courses, user } from '../../mocks/fixtures'
import { CoursePage } from './CoursePage'
afterEach(() => vi.restoreAllMocks())
it('按名称与状态筛选已加载作业，清除后恢复全部记录', async () => {
  vi.spyOn(api, 'session').mockResolvedValue({
    authenticated: true,
    user,
    csrf_token: 'test',
    server_time: '2026-11-05T00:00:00Z',
  })
  vi.spyOn(api, 'course').mockResolvedValue(courses[0])
  vi.spyOn(api, 'assignments').mockResolvedValue({ items: assignments, next_cursor: null })
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={['/courses/course-a']}>
        <Routes>
          <Route path="/courses/:id" element={<CoursePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  await screen.findByRole('link', { name: '分支与循环' })
  await userEvent.type(screen.getByRole('searchbox', { name: '搜索作业' }), '数组')
  expect(screen.queryByRole('link', { name: '分支与循环' })).toBeNull()
  expect(screen.getByRole('link', { name: '数组与字符串' })).toBeVisible()
  await userEvent.selectOptions(screen.getByLabelText('作业状态'), 'CLOSED')
  expect(screen.getByText('没有符合条件的作业，请调整或清除筛选。')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '清除筛选' }))
  expect(screen.getByRole('link', { name: '分支与循环' })).toBeVisible()
  expect(screen.getByText('显示 3 项 · 已加载 3 项')).toBeVisible()
})
