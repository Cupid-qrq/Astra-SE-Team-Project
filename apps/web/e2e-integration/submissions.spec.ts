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

test('前端契约样例：跨轮次帮助丢弃错配并支持读取失败重试', async ({ page }, info) => {
  test.skip(!process.env.ASTRA_SERVER_PYTHON, 'A独立host不包含B结果页')
  const id = 'a0000000-0000-4000-8000-000000000001'
  let reads = 0
  let helps = 0
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    if (!['warning', 'error'].includes(message.type())) return
    if (
      message.location().url.includes(`/submissions/${id}/feedback`) &&
      message.text().includes('503')
    )
      return
    errors.push(message.text())
  })
  await page.route(`**/api/v1/submissions/${id}`, (route) => {
    const current = ++reads > 1
    return route.fulfill({
      json: {
        submission_id: id,
        assignment_id: id,
        problem_id: id,
        state: 'FINISHED',
        verdict: current ? 'RE' : 'WA',
        mode: 'FORMAL',
        generation: current ? 2 : 1,
        attempt_id: current ? 'attempt-2' : 'attempt-1',
        feedback_version_id: current ? 'feedback-2' : 'feedback-1',
        time_ms: null,
        memory_bytes: null,
        case_results: [],
        language_key: 'python3',
        code: '# synthetic UI contract example',
        accepted_at: '2026-11-03T08:00:00Z',
      },
    })
  })
  await page.route(`**/api/v1/submissions/${id}/attempts*`, (route) =>
    route.fulfill({ json: { items: [], next_cursor: null } }),
  )
  await page.route(`**/api/v1/submissions/${id}/feedback`, (route) => {
    if (++helps === 1)
      return route.fulfill({
        status: 503,
        json: { error: { code: 'TEMPORARY', message: '帮助暂不可用' } },
      })
    return route.fulfill({
      json: {
        feedback_version_id: 'feedback-2',
        title: '新轮运行错误帮助',
        explanation: '检查数组边界。',
        checklist: [],
      },
    })
  })
  await page.addInitScript(() => {
    const observed: string[] = []
    Object.assign(window, { helpMismatches: observed })
    new MutationObserver(() => {
      const verdict = document.querySelector('[aria-label="评测结果"] h3')?.textContent
      const help = document.querySelector('[aria-label="固定帮助"] h3')?.textContent
      if (verdict === '答案错误' && help === '新轮运行错误帮助') observed.push('mismatch')
    }).observe(document, { subtree: true, childList: true, characterData: true })
  })
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill('student_a')
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('link', { name: '编辑器测试课程', exact: true })).toBeVisible()
  await page.goto(`/submissions/${id}`)
  await expect(page.getByRole('button', { name: '重新读取本轮帮助' })).toBeVisible()
  await page.getByRole('button', { name: '重新读取本轮帮助' }).click()
  await expect(page.getByRole('heading', { name: '新轮运行错误帮助' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '运行错误', exact: true })).toBeVisible()
  await expect(page.getByText('第 2 轮', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => Reflect.get(window, 'helpMismatches'))).toEqual([])
  await expect(page).toHaveTitle(/Astra/)
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
  await page.screenshot({
    path: `../../.local/feedback-race-${info.project.name}.png`,
    fullPage: true,
  })
})
