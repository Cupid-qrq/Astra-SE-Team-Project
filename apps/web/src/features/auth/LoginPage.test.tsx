import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, it } from 'vitest'
import { LoginPage } from './LoginPage'

it('退出后本机草稿清理失败的提示仍可见', () => {
  sessionStorage.setItem('astra.draftCleanupWarning', '本机草稿清理失败，请清除站点数据。')
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  expect(screen.getByRole('alert')).toHaveTextContent('本机草稿清理失败')
  sessionStorage.removeItem('astra.draftCleanupWarning')
})
