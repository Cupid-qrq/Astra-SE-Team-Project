import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../../app/runtime'
import { CreateCourseForm } from './CourseForms'

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
