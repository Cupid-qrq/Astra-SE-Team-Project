import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../../app/runtime'
import { VersionMaterials } from './VersionMaterials'
import { MemoryRouter, useLocation, Link } from 'react-router-dom'
import { teaching } from '../integrations/teaching'
import type { components } from '../../lib/api/schema'

afterEach(() => vi.restoreAllMocks())
it('未保存的参考程序不能被语言切换或重新载入静默丢弃，保存时暂停编辑', async () => {
  vi.spyOn(api, 'testcases').mockResolvedValue({ items: [], next_cursor: null })
  vi.spyOn(api, 'references').mockResolvedValue({ items: [], next_cursor: null })
  vi.spyOn(api, 'putReference').mockReturnValue(new Promise(() => {}))
  const version = {
    version_id: 'version',
    published_at: null,
    profile: { languages: [{ language_key: 'cpp17' }, { language_key: 'python3' }] },
  } as components['schemas']['ProblemVersion']
  render(
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient()}>
        <VersionMaterials
          version={version}
          revision={1}
          onRevision={() => {}}
          reload={async () => {}}
          unsaved={false}
        />
      </QueryClientProvider>
    </MemoryRouter>,
  )
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('参考程序'), '// reference')
  expect(screen.getByLabelText('参考语言')).toBeDisabled()
  expect(screen.getByRole('button', { name: '载入已保存参考程序' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: '保存参考程序' }))
  expect(screen.getByLabelText('参考程序')).toBeDisabled()
  expect(screen.getByLabelText('参考程序')).toHaveValue('// reference')
})

const versionId = '10000000-0000-4000-8000-000000000011'
const jobId = '10000000-0000-4000-8000-000000000012'
const detail = {
  version_revision: 1,
  current_revision: 1,
  matches_current: true,
  summary: null,
  preflight_id: jobId,
  version_id: versionId,
  content_digest: 'a'.repeat(64),
  profile_hash: 'b'.repeat(64),
  state: 'QUEUED' as const,
  cases: [],
}
function Location() {
  return <output data-testid="search">{useLocation().search}</output>
}
function materials(search = '', revision = 1, providedClient?: QueryClient) {
  vi.spyOn(api, 'testcases').mockResolvedValue({ items: [], next_cursor: null })
  vi.spyOn(api, 'references').mockResolvedValue({ items: [], next_cursor: null })
  const version = {
    version_id: versionId,
    published_at: null,
    profile: { languages: [{ language_key: 'cpp17' }] },
  } as components['schemas']['ProblemVersion']
  return render(
    <MemoryRouter initialEntries={['/version' + search]}>
      <QueryClientProvider
        client={
          providedClient || new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <VersionMaterials
          version={version}
          revision={revision}
          onRevision={() => {}}
          reload={async () => {}}
          unsaved={false}
        />
        <Location />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

it('已受理任务在URL保留指针，刷新可以恢复真实查询', async () => {
  vi.spyOn(teaching.preflight, 'enqueue').mockResolvedValue(detail)
  vi.spyOn(teaching.preflight, 'read').mockResolvedValue(detail)
  const view = materials()
  await userEvent.click(screen.getByRole('button', { name: '启动预检' }))
  expect(await screen.findByText('预检状态：QUEUED')).toBeVisible()
  expect(screen.getByTestId('search').textContent).toContain('preflight=' + jobId)
  view.unmount()
  const read = vi.mocked(teaching.preflight.read)
  read.mockClear()
  materials('?preflight=' + jobId + '&preflightRevision=1')
  expect(await screen.findByText('预检状态：QUEUED')).toBeVisible()
  expect(read).toHaveBeenCalledWith(jobId)
})

it('旧revision任务指针不能轮询或解锁发布', () => {
  const read = vi
    .spyOn(teaching.preflight, 'read')
    .mockResolvedValue({ ...detail, state: 'PASSED' })
  materials('?preflight=' + jobId + '&preflightRevision=1', 2)
  expect(read).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: '发布题目版本' })).toBeDisabled()
})

it('不同版本的任务响应不得展示通过或解锁发布', async () => {
  vi.spyOn(teaching.preflight, 'read').mockResolvedValue({
    ...detail,
    version_id: 'other',
    state: 'PASSED',
  })
  materials('?preflight=' + jobId + '&preflightRevision=1')
  expect(await screen.findByRole('alert')).toHaveTextContent('版本不匹配')
  expect(screen.queryByText('预检状态：PASSED')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '发布题目版本' })).toBeDisabled()
})

it('未保存参考程序时不能发送预检请求', async () => {
  const enqueue = vi.spyOn(teaching.preflight, 'enqueue').mockResolvedValue(detail)
  materials()
  await userEvent.type(screen.getByLabelText('参考程序'), 'unsaved')
  expect(screen.getByRole('button', { name: '启动预检' })).toBeDisabled()
  expect(enqueue).not.toHaveBeenCalled()
})

it('失败状态展示安全摘要且不能发布', async () => {
  vi.spyOn(teaching.preflight, 'read').mockResolvedValue({
    ...detail,
    state: 'FAILED',
    summary: 'cpp17 HIDDEN 1：WA',
  })
  materials('?preflight=' + jobId + '&preflightRevision=1')
  expect(await screen.findByText(/预检状态：FAILED/)).toHaveTextContent('WA')
  expect(screen.getByRole('button', { name: '发布题目版本' })).toBeDisabled()
})

it('篡改URL为当前修订也不能采用服务端判定不匹配的旧通过任务', async () => {
  vi.spyOn(teaching.preflight, 'read').mockResolvedValue({
    ...detail,
    state: 'PASSED',
    version_revision: 1,
    current_revision: 2,
    matches_current: false,
  })
  materials('?preflight=' + jobId + '&preflightRevision=2', 2)
  expect(await screen.findByRole('alert')).toHaveTextContent('内容已变更')
  expect(screen.queryByText('预检状态：PASSED')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '发布题目版本' })).toBeDisabled()
})

it('修订变化后不得复用新鲜缓存中的旧通过状态', async () => {
  vi.spyOn(api, 'testcases').mockResolvedValue({ items: [], next_cursor: null })
  vi.spyOn(api, 'references').mockResolvedValue({ items: [], next_cursor: null })
  const read = vi.spyOn(teaching.preflight, 'read').mockResolvedValue({
    ...detail,
    state: 'PASSED',
    version_revision: 1,
    current_revision: 1,
    matches_current: true,
  })
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 15000 } },
  })
  const version = {
    version_id: versionId,
    published_at: null,
    profile: { languages: [{ language_key: 'cpp17' }] },
  } as components['schemas']['ProblemVersion']
  function Root({ revision }: { revision: number }) {
    return (
      <MemoryRouter initialEntries={['/version?preflight=' + jobId + '&preflightRevision=1']}>
        <QueryClientProvider client={client}>
          <VersionMaterials
            version={version}
            revision={revision}
            onRevision={() => {}}
            reload={async () => {}}
            unsaved={false}
          />
          <Link to={'/version?preflight=' + jobId + '&preflightRevision=2'}>打开新修订</Link>
        </QueryClientProvider>
      </MemoryRouter>
    )
  }
  const view = render(<Root revision={1} />)
  expect(await screen.findByText('预检状态：PASSED')).toBeVisible()
  await userEvent.type(screen.getByLabelText('发布理由'), '核对全部材料并确认预检匹配后发布')
  expect(screen.getByRole('button', { name: '发布题目版本' })).toBeEnabled()
  read.mockResolvedValue({
    ...detail,
    state: 'PASSED',
    version_revision: 1,
    current_revision: 2,
    matches_current: false,
  })
  view.rerender(<Root revision={2} />)
  await userEvent.click(screen.getByRole('link', { name: '打开新修订' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('内容已变更')
  expect(screen.queryByText('预检状态：PASSED')).not.toBeInTheDocument()
})

it('后台重新核对失败时不能继续展示缓存的通过状态', async () => {
  const read = vi.spyOn(teaching.preflight, 'read').mockResolvedValue({
    ...detail,
    state: 'PASSED',
    version_revision: 1,
    current_revision: 1,
    matches_current: true,
  })
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 15000 } },
  })
  materials('?preflight=' + jobId + '&preflightRevision=1', 1, client)
  expect(await screen.findByText('预检状态：PASSED')).toBeVisible()
  await userEvent.type(screen.getByLabelText('发布理由'), '核对全部材料并确认预检匹配后发布')
  expect(screen.getByRole('button', { name: '发布题目版本' })).toBeEnabled()
  read.mockResolvedValue({
    ...detail,
    state: 'PASSED',
    version_revision: 1,
    current_revision: 2,
    matches_current: false,
  })
  await client.invalidateQueries({ queryKey: ['preflight'] })
  expect(await screen.findByRole('alert')).toHaveTextContent('内容已变更')
  expect(screen.queryByText('预检状态：PASSED')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '发布题目版本' })).toBeDisabled()
})

it('原任务修订较早但服务端确认当前内容相同则仍可使用通过证据', async () => {
  vi.spyOn(teaching.preflight, 'read').mockResolvedValue({
    ...detail,
    state: 'PASSED',
    version_revision: 1,
    current_revision: 2,
    matches_current: true,
  })
  materials('?preflight=' + jobId + '&preflightRevision=2', 2)
  expect(await screen.findByText('预检状态：PASSED')).toBeVisible()
  await userEvent.type(screen.getByLabelText('发布理由'), '核对全部材料并确认当前摘要相同后发布')
  expect(screen.getByRole('button', { name: '发布题目版本' })).toBeEnabled()
})
