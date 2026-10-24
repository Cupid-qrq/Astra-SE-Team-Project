import { test, expect } from '@playwright/test'

async function login(page: import('@playwright/test').Page, name = 'demo_student') {
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill(name)
  await page.getByLabel('密码', { exact: true }).fill('ExamplePass123')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '我的课程' })).toBeVisible()
}
test('登录、课程详情、返回与退出；无运行错误和横向溢出', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await login(page)
  await expect(page).toHaveTitle('Astra · 课程编程学习平台')
  await page.getByRole('link', { name: '程序设计基础' }).click()
  await expect(page.getByRole('heading', { name: '程序设计基础' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '分支与循环' })).toBeVisible()
  await page.getByRole('link', { name: '我的课程', exact: true }).first().click()
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
  await page.goto('/courses')
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  expect(errors).toEqual([])
})
test('登录错误保留账号，课程筛选提供空态', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill('bad_user')
  await page.getByLabel('密码', { exact: true }).fill('ExamplePass123')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('账号或密码不正确')
  await expect(page.getByLabel('账号', { exact: true })).toHaveValue('bad_user')
  await login(page)
  await page.getByLabel('搜索课程').fill('不存在的课程')
  await expect(page.getByText('没有匹配的课程，请调整搜索内容。')).toBeVisible()
})
test('会话失效清除旧页面；503 可主动重试', async ({ page }) => {
  await login(page, 'demo_expired')
  await page.getByRole('link', { name: '程序设计基础' }).click()
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
  await login(page, 'demo_unavailable')
  await expect(page.getByRole('alert')).toContainText('服务暂时不可用')
  await page.getByRole('button', { name: '重试' }).click()
  await expect(page.getByRole('link', { name: '程序设计基础' })).toBeVisible()
})
test('键盘与减少动态、缩放和截图', async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await login(page)
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: '跳到主要内容' })).toBeFocused()
  await page.keyboard.press('Escape')
  await page.getByRole('heading', { name: '我的课程' }).click()
  await page.screenshot({ path: testInfo.outputPath('courses.png'), fullPage: true })
  await page.evaluate(() => {
    document.documentElement.style.fontSize = '200%'
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
})
