import { openCourse } from './course-navigation'
import { expect, test, type Page } from '@playwright/test'

async function login(page: Page, name: string) {
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill(name)
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('button', { name: '退出登录', exact: true })).toBeVisible()
}

test('真实数据库：课程帮助草稿、预览、发布与冻结历史', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await login(page, 'teacher_a')
  const title = `帮助维护-${crypto.randomUUID().slice(0, 8)}`
  await page.getByLabel('新课程名称').fill(title)
  await page.getByRole('button', { name: '创建课程', exact: true }).click()
  await expect(page.getByText('课程已创建。', { exact: true })).toBeVisible()
  await openCourse(page, title)
  await page.getByRole('link', { name: '管理固定帮助', exact: true }).click()
  await page.getByRole('button', { name: '新建固定帮助', exact: true }).click()
  await page.getByLabel('帮助标题', { exact: true }).fill('边界检查第一版')
  await page.getByLabel('帮助说明', { exact: true }).fill('先检查**空输入**。')
  await page.getByLabel('检查清单（每行一项）').fill('手工核算最小样例\n检查重复值')
  await page.getByRole('button', { name: '创建草稿', exact: true }).click()
  await expect(page.getByRole('heading', { name: '编辑固定帮助', exact: true })).toBeVisible()
  await expect(page.getByText('尚未发布', { exact: true })).toBeVisible()
  await page.getByLabel('发布理由').fill('已经核对本课教学目标与检查方向')
  await page.getByRole('button', { name: '发布新版本', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: '确认发布', exact: true }).click()
  await expect(page.getByText('生效版本：1', { exact: true })).toBeVisible()
  await page.getByLabel('帮助标题', { exact: true }).fill('边界检查第二版')
  await page.getByRole('button', { name: '保存草稿', exact: true }).click()
  await expect(page.getByText('草稿已保存，尚未发布。', { exact: true })).toBeVisible()
  await page.getByLabel('发布理由').fill('根据本课反馈补充检查方向并核对')
  await page.getByRole('button', { name: '发布新版本', exact: true }).click()
  await page.getByRole('button', { name: '确认发布', exact: true }).click()
  await expect(page.getByText('生效版本：2', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '查看版本 1', exact: true }).click()
  await expect(
    page
      .getByRole('region', { name: '历史版本预览' })
      .getByRole('heading', { name: '边界检查第一版' }),
  ).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: info.outputPath('feedback-editor.png'), fullPage: true })
  await page.getByLabel('帮助标题', { exact: true }).fill('刷新前未保存的编辑')
  await page.reload()
  await expect(page.getByLabel('帮助标题', { exact: true })).toHaveValue('边界检查第二版')
  await page.getByRole('button', { name: '恢复本地编辑', exact: true }).click()
  await expect(page.getByLabel('帮助标题', { exact: true })).toHaveValue('刷新前未保存的编辑')
})

test('管理员可维护全局帮助，学生不能进入维护页面', async ({ page }) => {
  await login(page, 'admin_a')
  await page.getByRole('link', { name: '全局固定帮助', exact: true }).click()
  await expect(page.getByRole('heading', { name: '全局固定帮助', exact: true })).toBeVisible()
  await page.getByRole('table', { name: '固定帮助目录' }).getByRole('link').first().click()
  await expect(page.getByRole('heading', { name: '编辑固定帮助', exact: true })).toBeVisible()
  await expect(page.getByLabel('帮助标题', { exact: true })).toBeEditable()
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await login(page, 'student_a')
  await expect(page.getByRole('link', { name: '固定帮助维护', exact: true })).toHaveCount(0)
  await page.goto('/teacher/feedback')
  await expect(page.getByRole('heading', { name: '无权维护固定帮助', exact: true })).toBeVisible()
})

test('真实会话失效：重新登录后恢复新建帮助正文与选项', async ({ page }) => {
  await login(page, 'teacher_a')
  const title = `会话恢复-${crypto.randomUUID().slice(0, 8)}`
  await page.getByLabel('新课程名称').fill(title)
  await page.getByRole('button', { name: '创建课程', exact: true }).click()
  await expect(page.getByText('课程已创建。', { exact: true })).toBeVisible()
  await openCourse(page, title)
  await page.getByRole('link', { name: '管理固定帮助', exact: true }).click()
  const returnUrl = page.url()
  await page.getByRole('button', { name: '新建固定帮助', exact: true }).click()
  await page.getByLabel('判定类别', { exact: true }).selectOption('RE')
  await page.getByLabel('适用语言', { exact: true }).selectOption('python3')
  await page.getByLabel('帮助标题', { exact: true }).fill('会话失效前写好的标题')
  await page.getByLabel('帮助说明', { exact: true }).fill('需要保留的较长说明。')
  // Revoke this real server-side session without unmounting the current form.
  await page.evaluate(async () => {
    const session = await fetch('/api/v1/auth/session').then((response) => response.json())
    const response = await fetch('/api/v1/auth/logout', {
      method: 'POST',
      headers: { 'X-CSRF-Token': session.csrf_token },
    })
    if (response.status !== 204) throw new Error('Test session revocation failed')
  })
  await page.getByRole('button', { name: '创建草稿', exact: true }).click()
  await expect(page.getByRole('heading', { name: '欢迎回来', exact: true })).toBeVisible()
  await login(page, 'teacher_a')
  await page.goto(returnUrl)
  await page.getByRole('button', { name: '新建固定帮助', exact: true }).click()
  await page.getByRole('button', { name: '恢复新建草稿', exact: true }).click()
  await expect(page.getByLabel('帮助标题', { exact: true })).toHaveValue('会话失效前写好的标题')
  await expect(page.getByLabel('帮助说明', { exact: true })).toHaveValue('需要保留的较长说明。')
  await expect(page.getByLabel('判定类别', { exact: true })).toHaveValue('RE')
  await expect(page.getByLabel('适用语言', { exact: true })).toHaveValue('python3')
  await page.getByRole('button', { name: '创建草稿', exact: true }).click()
  await expect(page.getByRole('heading', { name: '编辑固定帮助', exact: true })).toBeVisible()
})
