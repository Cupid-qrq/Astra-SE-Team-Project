import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'

test('正式数据库提交到结果与历史，执行端使用明确的测试替身', async ({ page }, info) => {
  test.skip(!process.env.ASTRA_SERVER_PYTHON, 'A独立验证环境没有B提交Worker')
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill('student_a')
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('link', { name: '编辑器测试课程', exact: true }).click()
  await page.getByRole('link', { name: '编辑器固定作业', exact: true }).click()
  const assignmentUrl = page.url()
  await page.getByRole('link', { name: '开始编程', exact: true }).click()
  const session = await (await page.request.get('/api/v1/auth/session')).json()
  const match = new URL(page.url()).pathname.match(/assignments\/([^/]+)\/problems\/([^/]+)/)!
  const body = {
    assignment_id: match[1],
    problem_id: match[2],
    language_key: 'python3',
    code: '# public browser worker fixture\nprint(1)',
  }
  // The existing editor intentionally offers read-only mobile mode.
  const response = await page.request.post('/api/v1/submissions', {
    data: body,
    headers: {
      Origin: 'https://localhost:4175',
      'X-CSRF-Token': session.csrf_token,
      'Idempotency-Key': crypto.randomUUID(),
      'X-Submission-Intent': 'FORMAL',
    },
  })
  expect(response.status()).toBe(202)
  const receipt = await response.json()
  execFileSync(
    process.env.ASTRA_SERVER_PYTHON!,
    ['../../server/tests/shared/browser_submission_worker.py'],
    { env: process.env, timeout: 30000 },
  )
  await page.goto(`/submissions/${receipt.submission_id}`)
  await expect(page.getByRole('heading', { name: '提交详情', exact: true })).toBeVisible()
  await expect(page.getByText('评测完成', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '通过', exact: true })).toBeVisible()
  await expect(page.getByLabel('本次提交源码')).toHaveValue(body.code)
  await page.getByRole('link', { name: '返回提交历史' }).click()
  await page.getByLabel('筛选判定').selectOption('AC')
  await expect(page.getByRole('link').filter({ hasText: 'python3' }).first()).toBeVisible()
  await page.getByLabel('筛选判定').selectOption('WA')
  await expect(page.getByRole('heading', { name: '暂无符合条件的提交' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({
    path: `../../.local/submission-history-${info.project.name}.png`,
    fullPage: true,
  })
  await page.goto(assignmentUrl)
})
