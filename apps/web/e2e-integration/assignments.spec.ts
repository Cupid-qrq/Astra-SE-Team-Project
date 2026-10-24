import { expect, test } from '@playwright/test'

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
  await expect(page.getByText('提交服务尚未接入。', { exact: true })).toBeVisible()
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
