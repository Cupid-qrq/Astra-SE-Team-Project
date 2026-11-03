import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../../app/runtime'
import type { components } from '../../lib/api/schema'
import { CreateVersionPage, VersionPage } from './ProblemPages'

afterEach(() => vi.restoreAllMocks())
const version = {
  version_id: '10000000-0000-4000-8000-000000000011',
  problem_id: '10000000-0000-4000-8000-000000000012',
  title: '原题面',
  statement: '原说明',
  samples: [{ input: '1 2', output: '3' }],
  tags: ['加法'],
  source_ref: '',
  profile: {
    profile_id: '10000000-0000-4000-8000-000000000013',
    languages: [{ language_key: 'python3', version: '3' }],
  },
  revision: 1,
  published_at: null,
} as components['schemas']['ProblemVersion']

function setup(copy = false) {
  vi.spyOn(api, 'version').mockResolvedValue(version)
  vi.spyOn(api, 'testcases').mockResolvedValue({ items: [], next_cursor: null })
  vi.spyOn(api, 'references').mockResolvedValue({ items: [], next_cursor: null })
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter
        initialEntries={[
          copy
            ? `/new/${version.problem_id}?base=${version.version_id}`
            : `/version/${version.version_id}`,
        ]}
      >
        <Routes>
          <Route path="/version/:id" element={<VersionPage />} />
          <Route path="/new/:id" element={<CreateVersionPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return cache
}

it('无本地编辑时重新读取同步题面与修订，不显示旧内容已保存', async () => {
  const cache = setup()
  expect(await screen.findByLabelText('题目标题')).toHaveValue('原题面')
  act(() =>
    cache.setQueryData(['version', version.version_id], {
      ...version,
      revision: 2,
      title: '另一标签更新的题面',
      statement: '新说明',
    }),
  )
  await waitFor(() => expect(screen.getByLabelText('题目标题')).toHaveValue('另一标签更新的题面'))
  expect(screen.getByLabelText('题目说明')).toHaveValue('新说明')
  expect(screen.getByText('草稿 · 修订 2')).toBeVisible()
  expect(screen.getByRole('button', { name: '启动预检' })).toBeEnabled()
})

it('外部修订保留本地输入，保存前阻止预检，保存只提交内容字段', async () => {
  const cache = setup()
  const user = userEvent.setup()
  await user.clear(await screen.findByLabelText('题目标题'))
  await user.type(screen.getByLabelText('题目标题'), '我的未保存内容')
  act(() =>
    cache.setQueryData(['version', version.version_id], {
      ...version,
      revision: 2,
      title: '服务器新题面',
    }),
  )
  await waitFor(() => expect(screen.getByRole('heading', { name: '服务器新题面' })).toBeVisible())
  expect(screen.getByLabelText('题目标题')).toHaveValue('我的未保存内容')
  expect(screen.getByRole('button', { name: '启动预检' })).toBeDisabled()
  expect(screen.queryByText('题面已保存。')).not.toBeInTheDocument()
  vi.mocked(api.version).mockResolvedValue({
    ...version,
    revision: 3,
    title: '我的未保存内容',
  })
  const update = vi.spyOn(api, 'updateVersion').mockResolvedValue({ revision: 3 })
  await user.click(screen.getByRole('button', { name: '保存题面' }))
  await waitFor(() => expect(update).toHaveBeenCalled())
  const body = update.mock.calls[0][1]
  expect(Object.keys(body).sort()).toEqual([
    'expected_revision',
    'profile',
    'samples',
    'source_ref',
    'statement',
    'tags',
    'title',
  ])
  expect(body.expected_revision).toBe(2)
  expect(body.title).toBe('我的未保存内容')
})

it('复制版本只提交可编辑内容与明确的来源ID，不携带旧版本元数据', async () => {
  vi.spyOn(api, 'profiles').mockResolvedValue({ items: [version.profile], next_cursor: null })
  const create = vi.spyOn(api, 'createVersion').mockReturnValue(new Promise(() => {}))
  setup(true)
  await screen.findByLabelText('题目标题')
  await userEvent.click(screen.getByRole('button', { name: '保存题面' }))
  await waitFor(() => expect(create).toHaveBeenCalled())
  expect(Object.keys(create.mock.calls[0][0]).sort()).toEqual([
    'base_version_id',
    'problem_id',
    'profile',
    'samples',
    'source_ref',
    'statement',
    'tags',
    'title',
  ])
})
