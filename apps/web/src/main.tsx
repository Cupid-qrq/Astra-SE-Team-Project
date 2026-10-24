import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { App } from './app/App'
import { queryClient } from './app/runtime'
import './styles/tokens.css'
import './styles/app.css'

async function start() {
  if (__MOCK__) {
    const { worker } = await import('./mocks/browser')
    await worker.start({ quiet: true, onUnhandledFrame: 'bypass' })
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}
void start().catch(() => {
  document.getElementById('root')!.textContent = '应用启动失败，请刷新后重试。'
})
