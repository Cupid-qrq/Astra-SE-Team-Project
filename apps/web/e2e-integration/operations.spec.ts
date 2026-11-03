import { expect, test, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import os from 'node:os'

function fixture(file: string, args: string[] = []) {
  return execFileSync(
    process.env.ASTRA_SERVER_PYTHON!,
    [`../../server/tests/shared/${file}`, ...args],
    {
      env: process.env,
      timeout: 30000,
      encoding: 'utf8',
    },
  )
}

async function login(page: Page, role: string) {
  if (await page.getByRole('button', { name: '退出登录', exact: true }).count()) {
    await page.getByRole('button', { name: '退出登录', exact: true }).click()
  }
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill(`${role}_a`)
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('button', { name: '退出登录', exact: true })).toBeVisible()
}

test('正式成绩发布理由校验与管理员登录入口（执行替身）', async ({ page }, info) => {
  test.skip(!process.env.ASTRA_SERVER_PYTHON, 'Requires formal PostgreSQL host')
  test.setTimeout(150000)
  const ids = JSON.parse(fixture('browser_operations_fixture.py')) as Record<string, string>
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => {
    if (['error', 'warning'].includes(m.type())) errors.push(m.text())
  })
  const evidence = path.join(os.tmpdir(), 'astra-operations-qa')
  mkdirSync(evidence, { recursive: true })
  async function screenshot(name: string) {
    expect(await page.title()).toContain('Astra')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await expect(page.locator('vite-error-overlay')).toHaveCount(0)
    await page.screenshot({
      path: path.join(evidence, `${name}-${info.project.name}.png`),
      fullPage: true,
    })
  }
  await login(page, 'student')
  const session = await (await page.request.get('/api/v1/auth/session')).json()
  const submission = await page.request.post('/api/v1/submissions', {
    data: {
      assignment_id: ids.assignment,
      problem_id: ids.problem,
      language_key: 'python3',
      code: '# public browser worker fixture\nprint(1)',
    },
    headers: {
      Origin: 'https://localhost:4175',
      'X-CSRF-Token': session.csrf_token,
      'Idempotency-Key': crypto.randomUUID(),
      'X-Submission-Intent': 'FORMAL',
    },
  })
  expect(submission.status()).toBe(202)
  fixture('browser_submission_worker.py')
  fixture('browser_operations_fixture.py', [ids.assignment!])

  await login(page, 'teacher')
  await page.goto(`/assignments/${ids.assignment}`)
  await page.getByRole('link', { name: '查看作业成绩' }).click()
  await expect(page.getByRole('heading', { name: '总分 100', exact: true })).toBeVisible()
  await page.getByLabel('成绩发布理由').fill('浏览器联调成绩核对')
  await expect(page.getByRole('button', { name: '发布成绩', exact: true })).toBeDisabled()
  await page.getByLabel('成绩发布理由').fill('浏览器联调成绩核对确认')
  await page.getByRole('button', { name: '发布成绩', exact: true }).click()
  await page.getByRole('button', { name: '确认发布', exact: true }).click()
  await expect(page.getByText('已发布成绩', { exact: true })).toBeVisible()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出当前成绩CSV' }).click()
  expect((await downloadPromise).suggestedFilename()).toMatch(/^astra-grades-.+\.csv$/)
  await screenshot('teacher-grades')
  await login(page, 'admin')
  await expect.soft(page).toHaveURL(/\/admin\/operations$/)
  await page.getByRole('link', { name: '平台管理', exact: true }).click()
  await expect(page.getByText('数据库 READY', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '账号', exact: true }).click()
  await page.getByLabel('管理操作理由').fill('短理由')
  await page.getByLabel('登录账号', { exact: true }).fill(`qa_${crypto.randomUUID().slice(0, 8)}`)
  await page.getByLabel('显示名称', { exact: true }).fill('联调账号')
  await page.getByLabel('初始或重置密码').fill('BrowserOnlyPassword123!')
  await expect.soft(page.getByRole('button', { name: '创建账号', exact: true })).toBeDisabled()
  await page.getByLabel('管理操作理由').fill('浏览器联调账号创建核对确认')
  await page.getByRole('button', { name: '创建账号', exact: true }).click()
  await expect(page.getByText('操作已完成。', { exact: true })).toBeVisible()
  await screenshot('admin-accounts')
  await login(page, 'student')
  await page.goto(`/assignments/${ids.assignment}/grades`)
  await expect(page.getByRole('heading', { name: '总分 100', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '发布成绩', exact: true })).toHaveCount(0)
  expect(errors).toEqual([])
})
