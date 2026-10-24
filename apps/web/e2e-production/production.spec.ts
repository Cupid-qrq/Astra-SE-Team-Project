import { test, expect } from '@playwright/test'
import { user, courses } from '../src/mocks/fixtures'

test('会话轮询切换身份后卸载旧账户内容并读取新账户数据', async ({ page }) => {
  await page.clock.install()
  let switched = false
  await page.route('**/api/v1/auth/session', (route) =>
    route.fulfill({
      json: {
        authenticated: true,
        user: switched
          ? { ...user, user_id: '99999999-9999-4999-8999-999999999999', display_name: '新同学' }
          : user,
        csrf_token: 'test-csrf',
        server_time: '2026-10-24T00:00:00.000Z',
      },
    }),
  )
  await page.route('**/api/v1/courses', (route) =>
    route.fulfill({ json: { items: switched ? [] : courses, next_cursor: null } }),
  )
  await page.goto('/courses')
  await expect(page.getByRole('link', { name: '程序设计基础' })).toBeVisible()
  switched = true
  await page.clock.fastForward(60_001)
  await expect(page.getByText('新同学')).toBeVisible()
  await expect(page.getByText('暂未加入课程，请联系任课教师。')).toBeVisible()
  await expect(page.getByText('程序设计基础')).toHaveCount(0)
})

test('生产产物请求同源API，上游故障时明确报错且不启用Mock', async ({ page }) => {
  const requested: string[] = []
  const errors: string[] = []
  page.on('request', (request) => requested.push(request.url()))
  page.on('pageerror', (error) => errors.push(error.message))
  await page.route('**/api/v1/auth/session', (route) =>
    route.fulfill({ status: 503, contentType: 'text/plain', body: 'Upstream unavailable' }),
  )
  await page.goto('/courses')
  await expect(page.getByRole('alert')).toContainText('服务暂时不可用')
  expect(requested).toContain('http://127.0.0.1:4174/api/v1/auth/session')
  expect(
    await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length),
  ).toBe(0)
  await expect(page.getByText('演示 · 虚构数据')).toHaveCount(0)
  await expect(page.getByText('程序设计基础')).toHaveCount(0)
  expect(errors).toEqual([])
})
