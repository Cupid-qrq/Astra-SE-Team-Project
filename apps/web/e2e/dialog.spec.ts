import { test, expect } from '@playwright/test'

test('确认弹窗忙碌时键盘焦点留在弹窗并隔离背景', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
  await page.evaluate(async () => {
    const path = '/src/test/dialog-mount.ts'
    const harness = await import(path)
    const container = document.createElement('div')
    document.body.append(container)
    harness.mount(container)
  })
  await page.getByRole('button', { name: '测试确认操作' }).click()
  await expect(page.getByRole('button', { name: '取消' })).toBeFocused()
  await page.getByRole('button', { name: '执行测试' }).click()
  await expect(page.getByRole('dialog')).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('dialog')).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(page.getByRole('dialog')).toBeFocused()
  await expect(page.locator('#root')).toHaveAttribute('inert', '')
})
