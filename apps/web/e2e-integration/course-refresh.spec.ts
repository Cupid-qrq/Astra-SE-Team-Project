import { expect, test } from '@playwright/test'

test('真实数据库：首屏课程读取未结束时建课仍展示新课程', async ({ page }) => {
  let initialCaptured!: () => void
  let releaseInitial!: () => void
  const captured = new Promise<void>((resolve) => {
    initialCaptured = resolve
  })
  const release = new Promise<void>((resolve) => {
    releaseInitial = resolve
  })
  let first = true
  await page.route(/\/api\/v1\/courses(?:\?.*)?$/, async (route) => {
    if (route.request().method() === 'GET' && first) {
      first = false
      const response = await route.fetch()
      initialCaptured()
      await release
      await route.fulfill({ response })
    } else {
      await route.continue()
    }
  })
  try {
    await page.goto('/login')
    await page.getByLabel('账号', { exact: true }).fill('teacher_a')
    await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
    await page.getByRole('button', { name: '登录', exact: true }).click()
    await captured
    const title = `缓存竞态-${crypto.randomUUID().slice(0, 8)}`
    await page.getByLabel('新课程名称').fill(title)
    const created = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/api/v1/courses' &&
        response.request().method() === 'POST',
    )
    await page.getByRole('button', { name: '创建课程', exact: true }).click()
    expect((await created).status()).toBe(201)
    // Hold the old list until mutation success has actually invalidated the cache.
    await expect(page.getByText('课程已创建。', { exact: true })).toBeVisible()
    releaseInitial()
    await expect(page.getByRole('link', { name: title, exact: true })).toBeVisible()
  } finally {
    releaseInitial()
  }
})
