import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MotionProvider, MotionToggle } from './MotionEffects'

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  )
})
afterEach(() => vi.unstubAllGlobals())
it('暂停立即停止动效，偏好在重新挂载后保留', async () => {
  const view = render(
    <MotionProvider>
      <MotionToggle />
    </MotionProvider>,
  )
  await userEvent.click(screen.getByRole('button', { name: '暂停动态效果' }))
  expect(document.documentElement).toHaveAttribute('data-motion', 'off')
  expect(screen.getByRole('button', { name: '开启动态效果' })).toHaveAttribute(
    'aria-pressed',
    'false',
  )
  view.unmount()
  render(
    <MotionProvider>
      <MotionToggle />
    </MotionProvider>,
  )
  expect(screen.getByRole('button', { name: '开启动态效果' })).toHaveAttribute(
    'aria-pressed',
    'false',
  )
})
it('系统要求减少动态时保持静态，并说明当前设置', () => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  )
  render(
    <MotionProvider>
      <MotionToggle />
    </MotionProvider>,
  )
  expect(screen.getByRole('button', { name: '开启动态效果' })).toBeDisabled()
  expect(document.documentElement).toHaveAttribute('data-motion', 'off')
})
it('浏览器禁止保存偏好时仍能在当前页面暂停', async () => {
  const save = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('disabled')
  })
  render(
    <MotionProvider>
      <MotionToggle />
    </MotionProvider>,
  )
  await userEvent.click(screen.getByRole('button', { name: '暂停动态效果' }))
  expect(document.documentElement).toHaveAttribute('data-motion', 'off')
  save.mockRestore()
})
