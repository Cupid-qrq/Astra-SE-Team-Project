import { openCourse } from './course-navigation'
import { expect, test } from '@playwright/test'
import path from 'node:path'

test('正式预检：数据库任务刷新恢复，未知指针报错，修改材料后旧任务失效', async ({
  page,
}, testInfo) => {
  test.skip(!process.env.ASTRA_SERVER_PYTHON, 'B预检仅在正式服务host实测，A独立host不冒充B实现')
  const pageErrors: string[] = []
  const consoleErrors: string[] = []
  let missingId = ''
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('console', (message) => {
    if (
      message.type() === 'error' &&
      !(
        missingId &&
        message.location().url.includes('/preflights/' + missingId) &&
        message.text().includes('404')
      )
    )
      consoleErrors.push(message.text())
  })
  await page.goto('/login')
  await expect(page).toHaveTitle(/Astra/)
  await page.getByLabel('账号', { exact: true }).fill('teacher_a')
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  const course = `预检-${crypto.randomUUID().slice(0, 8)}`
  await page.getByLabel('新课程名称').fill(course)
  await page.getByRole('button', { name: '创建课程' }).click()
  await expect(page.getByText('课程已创建。', { exact: true })).toBeVisible()
  await openCourse(page, course)
  await page.getByRole('link', { name: '管理题目' }).click()
  await page.getByRole('button', { name: '新建题目' }).click()
  await page.getByLabel('题目标题').fill('预检持久化示例')
  await page.getByLabel('题目说明').fill('输入两个整数，输出它们的和。')
  await page.getByLabel('样例 1 输入').fill('1 2')
  await page.getByLabel('样例 1 输出').fill('3')
  await page.getByRole('button', { name: '保存题面' }).click()
  await expect(page.getByText('题面已保存。')).toBeVisible()
  await page.getByLabel('测试输入').fill('10 20')
  await page.getByLabel('预期答案').fill('30')
  await page.getByRole('button', { name: '保存配对测试' }).click()
  await expect(page.getByText('测试点已保存。')).toBeVisible()
  const languages = await page
    .getByLabel('参考语言')
    .locator('option')
    .evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value))
  expect(languages).toEqual(['cpp17', 'python3'])
  for (const language of languages) {
    await page.getByLabel('参考语言').selectOption(language)
    await page
      .getByLabel('参考程序')
      .fill(
        language === 'cpp17'
          ? '#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}'
          : 'print(sum(map(int,input().split())))',
      )
    const saved = page.waitForResponse(
      (response) =>
        response.request().method() === 'PUT' && response.url().endsWith('/references/' + language),
    )
    await page.getByRole('button', { name: '保存参考程序', exact: true }).click()
    expect((await saved).status()).toBe(200)
  }
  const posted = page.waitForResponse(
    (response) => response.request().method() === 'POST' && response.url().endsWith('/preflight'),
  )
  await page.getByRole('button', { name: '启动预检' }).click()
  const response = await posted
  expect(response.status()).toBe(202)
  const receipt = await response.json()
  await expect(page.getByText('预检状态：QUEUED')).toBeVisible()
  await expect(page.getByRole('list', { name: '预检测试进度' }).getByRole('listitem')).toHaveCount(
    4,
  )
  const savedUrl = page.url()
  expect(savedUrl).toContain('preflight=' + receipt.preflight_id)
  await page.reload()
  await expect(page.getByText('预检状态：QUEUED')).toBeVisible()
  await expect(page.getByRole('list', { name: '预检测试进度' }).getByRole('listitem')).toHaveCount(
    4,
  )
  const polled = page.waitForRequest(
    (request) =>
      request.method() === 'GET' && request.url().includes('/preflights/' + receipt.preflight_id),
  )
  expect((await polled).headers()['x-astra-background']).toBe('1')
  expect(await page.locator('vite-error-overlay').count()).toBe(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({
    path: path.resolve('../../.local', `preflight-ui-${testInfo.project.name}.png`),
    fullPage: true,
  })
  await page
    .getByRole('heading', { name: '预检与发布', exact: true })
    .locator('..')
    .screenshot({
      path: path.resolve('../../.local', `preflight-panel-${testInfo.project.name}.png`),
    })
  missingId = crypto.randomUUID()
  const badUrl = new URL(savedUrl)
  badUrl.searchParams.set('preflight', missingId)
  await page.goto(badUrl.toString())
  await expect(page.getByRole('alert')).toContainText('预检记录不存在或无权访问')
  await expect(page.getByRole('button', { name: '发布题目版本' })).toBeDisabled()
  await page.goto(savedUrl)
  await expect(page.getByText('预检状态：QUEUED')).toBeVisible()
  await page.getByRole('button', { name: '载入测试 1', exact: true }).click()
  await page.getByLabel('测试输入').fill('4 5')
  await page.getByLabel('预期答案').fill('9')
  await page.getByRole('button', { name: '保存配对测试' }).click()
  await expect(page.getByText('预检状态：QUEUED')).not.toBeVisible()
  await expect(page.getByRole('button', { name: '发布题目版本' })).toBeDisabled()
  expect(pageErrors).toEqual([])
  expect(consoleErrors).toEqual([])
})
