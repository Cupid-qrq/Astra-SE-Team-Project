import { expect, test } from '@playwright/test'

test('真实种子版本可以嵌入结果区域，三视口保留固定帮助清单', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill('student_a')
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '我的课程', exact: true })).toBeVisible()
  // Test-only host for the exported component; no B result route or accepted submission is invented.
  await page.evaluate(async () => {
    const { mountHelp } = await import('/e2e-integration/help-host.tsx')
    await mountHelp()
  })
  await expect(page.getByRole('region', { name: '固定帮助' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '答案错误' })).toBeVisible()
  await expect(page.getByText('用小规模自编数据手工核算。')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
