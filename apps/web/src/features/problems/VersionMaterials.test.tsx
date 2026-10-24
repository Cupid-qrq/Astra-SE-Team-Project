import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../../app/runtime'
import { VersionMaterials } from './VersionMaterials'
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
    <QueryClientProvider client={new QueryClient()}>
      <VersionMaterials
        version={version}
        revision={1}
        onRevision={() => {}}
        reload={async () => {}}
        unsaved={false}
      />
    </QueryClientProvider>,
  )
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('参考程序'), '// reference')
  expect(screen.getByLabelText('参考语言')).toBeDisabled()
  expect(screen.getByRole('button', { name: '载入已保存参考程序' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: '保存参考程序' }))
  expect(screen.getByLabelText('参考程序')).toBeDisabled()
  expect(screen.getByLabelText('参考程序')).toHaveValue('// reference')
})
