import { expect, test } from '@playwright/test'

test('前端契约样例：公平公告安全展示、状态更新、键盘与窄屏', async ({ page, browser }, info) => {
  const errors: string[] = []
  const consoleProblems: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    if (['error', 'warning'].includes(message.type())) consoleProblems.push(message.text())
  })
  const id = '10000000-0000-4000-8000-000000000001'
  let review = 'PENDING'
  let notice: string | null = null
  await page.route('**/api/v1/assignments/' + id, (route) =>
    route.fulfill({
      json: {
        assignment_id: id,
        course_id: id,
        title: '公告展示检查',
        state: 'OPEN',
        revision: 1,
        items: [],
        open_at: '2020-01-01T00:00:00.000Z',
        due_at: '2030-01-01T00:00:00.000Z',
        server_time: '2026-11-03T00:00:00.000Z',
        ai_policy: 'DISABLED',
        grade_state: 'PROVISIONAL',
        fairness_review: review,
        fairness_notice: notice,
      },
    }),
  )
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill('student_a')
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '我的课程', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: '编辑器测试课程', exact: true })).toBeVisible()
  await page.goto('/assignments/' + id)
  await expect(page).toHaveTitle('Astra · 课程编程学习平台')
  await expect(page).toHaveURL(new RegExp('/assignments/' + id + '$'))
  const announcement = page.getByRole('region', { name: '公平与作业公告' })
  await expect(announcement).toContainText('公平复核中')
  const skip = page.getByRole('link', { name: '跳到主要内容' })
  // Playwright's Windows WebKit defaults to tabbing form controls, skipping all links.
  // Check keyboard activation there; Chromium additionally checks natural Tab discovery.
  if (browser.browserType().name() === 'webkit') await skip.focus()
  else await page.keyboard.press('Tab')
  await expect(skip).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.locator('main')).toBeFocused()
  await page.screenshot({ path: info.outputPath('fairness-pending.png'), fullPage: true })
  review = 'RESOLVED'
  notice = '已统一延期，请以页面截止时间为准。\n<img src=x onerror=alert(1)> ' + 'x'.repeat(100)
  await page.reload()
  await expect(announcement).toContainText('公平复核已处理')
  await expect(announcement).toContainText('<img src=x onerror=alert(1)>')
  await expect(announcement.locator('img')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  expect(errors).toEqual([])
  expect(consoleProblems).toEqual([])
  await page.screenshot({ path: info.outputPath('fairness-resolved.png'), fullPage: true })
  console.log(`A fairness browser: ${browser.browserType().name()} ${browser.version()}`)
  review = 'NONE'
  notice = null
  await page.reload()
  await expect(page.getByRole('heading', { name: '公告展示检查' })).toBeVisible()
  await expect(announcement).toHaveCount(0)
})

test('真实数据库：创建发布作业并进入学生编辑器，异常保留代码和刷新恢复', async ({ page }, info) => {
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill('teacher_a')
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('link', { name: '编辑器测试课程', exact: true }).click()
  await page.getByRole('link', { name: '新建作业', exact: true }).click()
  const title = `作业-${info.project.name}-${crypto.randomUUID().slice(0, 5)}`
  await page.getByLabel('作业标题').fill(title)
  await page.getByLabel('开放时间（北京时间）').fill('2020-01-01T00:00')
  await page.getByLabel('截止时间（北京时间）').fill('2030-01-01T00:00')
  await page.getByLabel('选择题目 两数之和').check()
  await page.getByRole('button', { name: '保存作业草稿' }).click()
  await page.getByLabel('操作理由').fill('已核对题目版本分值与作业时间安排')
  await page.getByRole('button', { name: '发布作业', exact: true }).click()
  await page.getByRole('button', { name: '确认发布', exact: true }).click()
  await expect(page.getByText('作业已发布。')).toBeVisible()
  const url = page.url()
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await page.getByLabel('账号', { exact: true }).fill('student_a')
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '我的课程', exact: true })).toBeVisible()
  await page.goto(url)
  await page.getByRole('link', { name: '开始编程', exact: true }).click()
  await expect(page.locator('html')).toHaveCSS('color', 'rgb(36, 35, 32)')
  await expect(page.locator('.back-link')).toHaveCSS('text-decoration-line', 'none')
  await expect(page.locator('.skip-link')).toHaveCSS('top', '-100px')
  if (info.project.name === 'mobile') {
    await expect(page.getByText('手机端仅支持阅读题目和草稿，请在电脑上编程。')).toBeVisible()
    await expect(page.getByRole('button', { name: '提交代码', exact: true })).toBeDisabled()
    await page.screenshot({
      path: `../../.local/a-editor-${info.project.name}.png`,
      fullPage: true,
    })
    return
  }
  await page.getByLabel('编程语言').selectOption('python3')
  await page.getByRole('textbox', { name: '代码编辑器' }).fill('print(123)')
  await expect(page.getByText(/已保存于/)).toBeVisible()
  await page.getByRole('button', { name: '提交代码', exact: true }).click()
  if (process.env.ASTRA_SERVER_PYTHON) {
    await expect(page.getByRole('dialog', { name: '提交评测结果' })).toBeVisible()
    await expect(page.getByText('等待评测', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: '关闭结果' }).click()
  } else {
    await expect(page.getByRole('alert')).toBeVisible()
  }
  await expect(page.getByRole('textbox', { name: '代码编辑器' })).toHaveText('print(123)')
  await page.screenshot({ path: `../../.local/a-editor-${info.project.name}.png`, fullPage: true })
  await page.reload()
  await page.getByLabel('编程语言').selectOption('python3')
  await expect(page.getByRole('textbox', { name: '代码编辑器' })).toHaveText('print(123)')
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await expect(page.getByRole('button', { name: '导出本账户草稿' })).toBeVisible()
  await page.getByRole('button', { name: '退出并清除草稿' }).click()
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
})
