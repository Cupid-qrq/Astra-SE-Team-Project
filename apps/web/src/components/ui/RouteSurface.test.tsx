import { render, screen, act, fireEvent } from '@testing-library/react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { vi, it, expect, afterEach } from 'vitest'
import { RouteSurface } from './RouteSurface'
function Example() {
  const navigate = useNavigate()
  return (
    <RouteSurface>
      <input aria-label="草稿" defaultValue="保留我的代码" />
      <button onClick={() => navigate('/learning')}>学习</button>
      <button onClick={() => navigate('/courses')}>课程</button>
    </RouteSurface>
  )
}
afterEach(() => {
  vi.restoreAllMocks()
  delete document.documentElement.dataset.motion
})
it('快速切换取消旧动画并保留表单，暂停立即结束过渡', async () => {
  const cancel = vi.fn()
  const animate = vi.fn(() => ({ cancel }))
  Object.defineProperty(Element.prototype, 'animate', { configurable: true, value: animate })
  document.documentElement.dataset.motion = 'on'
  const view = render(
    <MemoryRouter>
      <Example />
    </MemoryRouter>,
  )
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: '学习' }))
  })
  expect(screen.getByLabelText('草稿')).toHaveValue('保留我的代码')
  expect(cancel).toHaveBeenCalled()
  const beforePause = cancel.mock.calls.length
  await act(async () => {
    document.documentElement.dataset.motion = 'off'
  })
  expect(cancel.mock.calls.length).toBeGreaterThan(beforePause)
  const calls = animate.mock.calls.length
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: '课程' }))
  })
  expect(animate).toHaveBeenCalledTimes(calls)
  view.unmount()
})
