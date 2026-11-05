import { openCourse } from './course-navigation'
import { expect, test, type Page } from '@playwright/test'
async function login(page: Page, account: string) {
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill(account)
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
}
async function createDraft(page: Page) {
  const courseId = new URL(page.url()).searchParams.get('course_id')
  const saved = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/v1/hint-templates',
  )
  await page.getByRole('button', { name: '创建草稿' }).click()
  const receipt = await saved
  expect(receipt.status()).toBe(201)
  const created = await receipt.json()
  await expect(page).toHaveURL(
    (url) =>
      url.pathname.endsWith(`/hint-templates/${created.template_id}`) &&
      url.searchParams.get('course_id') === courseId,
  )
}
async function confirmPublish(page: Page) {
  const published = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/hint-templates/') &&
      response.url().endsWith('/publish'),
  )
  await page.getByRole('button', { name: '确认发布' }).click()
  expect((await published).status()).toBe(200)
}
test('课程模板从草稿到冻结历史，刷新后可恢复修改', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await login(page, 'teacher_a')
  const title = 'AI 辅导设置-' + crypto.randomUUID().slice(0, 8)
  await page.getByLabel('新课程名称').fill(title)
  await page.getByRole('button', { name: '创建课程', exact: true }).click()
  await expect(page.getByText('课程已创建。', { exact: true })).toBeVisible()
  await openCourse(page, title)
  await page.getByRole('link', { name: '管理AI 辅导设置' }).click()
  await page.getByRole('button', { name: '新建AI 辅导设置' }).click()
  await page.getByLabel('给 AI 的指导要求').fill('第一版：阅读 {question}')
  await page.getByRole('checkbox', { name: '学生的问题 {question}', exact: true }).check()
  await expect(page.getByRole('region', { name: '要求预览' })).toContainText('我应该先检查哪个运算')
  await createDraft(page)
  await expect(page.getByRole('heading', { name: '编辑AI 辅导设置' })).toBeVisible()
  await page.getByLabel('发布理由').fill('教师已核对课程目标和要求预览')
  await page.getByRole('button', { name: '发布新版本' }).click()
  await confirmPublish(page)
  await expect(page.getByText(/最新发布版本 1/)).toBeVisible()
  await page.getByLabel('给 AI 的指导要求').fill('第二版：检查 {question}')
  await page.reload()
  await expect(page.getByLabel('给 AI 的指导要求')).toHaveValue('第一版：阅读 {question}')
  await page.getByRole('button', { name: '恢复本地编辑' }).click()
  await expect(page.getByLabel('给 AI 的指导要求')).toHaveValue('第二版：检查 {question}')
  await page.getByRole('button', { name: '保存草稿' }).click()
  await expect(page.getByRole('status')).toContainText('草稿已保存')
  await page.getByRole('button', { name: '查看版本 1' }).click()
  await expect(page.getByRole('region', { name: '已发布版本详情' })).toContainText(
    '第一版：阅读 {question}',
  )
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
  await page.screenshot({ path: info.outputPath('template-editor.png'), fullPage: true })
})
test('管理员可进入全局目录，学生不能读取模板维护页', async ({ page }) => {
  await login(page, 'admin_a')
  await page.getByRole('link', { name: '全局AI 辅导设置' }).click()
  await expect(page.getByRole('heading', { name: '全局AI 辅导设置' })).toBeVisible()
  const create = page.getByRole('button', { name: '新建AI 辅导设置' })
  const existing = page.getByRole('table', { name: 'AI 辅导设置目录' }).getByRole('link').first()
  await expect(create.or(existing).first()).toBeVisible()
  if (await create.isVisible()) {
    await create.click()
    await page.getByLabel('给 AI 的指导要求').fill('全局教学检查方向')
    await page.reload()
    await create.click()
    await page.getByRole('button', { name: '恢复本地编辑' }).click()
    await expect(page.getByLabel('给 AI 的指导要求')).toHaveValue('全局教学检查方向')
    await createDraft(page)
  } else {
    await existing.click()
  }
  await expect(page.getByRole('heading', { name: '编辑AI 辅导设置' })).toBeVisible()
  await page.getByLabel('发布理由').fill('全局管理员已核对此版教学提示内容')
  await page.getByRole('button', { name: '发布新版本' }).click()
  await confirmPublish(page)
  await expect(page.getByText('新版本已发布。')).toBeVisible()
  await page.getByRole('button', { name: '查看版本 1', exact: true }).click()
  await expect(page.getByRole('region', { name: '已发布版本详情' })).toContainText(
    '全局教学检查方向',
  )
  await page.getByRole('button', { name: '退出登录' }).click()
  await login(page, 'student_a')
  await expect(page.getByRole('link', { name: 'AI 辅导设置维护' })).toHaveCount(0)
  await page.goto('/teacher/hint-templates')
  await expect(page.getByRole('heading', { name: '无权维护AI 辅导设置' })).toBeVisible()
})
