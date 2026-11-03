import { openCourse } from './course-navigation'
import { expect, test } from '@playwright/test'
import path from 'node:path'

test('真实数据库：题目材料、跨标签题面同步与复制版本', async ({ page, context }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    if (!['error', 'warning'].includes(message.type())) return
    if (message.location().url.endsWith('/preflight') && /\b(404|409)\b/.test(message.text()))
      return
    errors.push(message.text())
  })
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill('teacher_a')
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  const course = `题库-${crypto.randomUUID().slice(0, 8)}`
  await page.getByLabel('新课程名称').fill(course)
  await page.getByRole('button', { name: '创建课程' }).click()
  await expect(page.getByText('课程已创建。', { exact: true })).toBeVisible()
  await openCourse(page, course)
  await page.getByRole('link', { name: '管理题目' }).click()
  await page.getByRole('button', { name: '新建题目' }).click()
  await page.getByLabel('题目标题').fill('两数之和')
  await page.getByLabel('题目说明').fill('输入两个整数，输出它们的和。')
  await page.getByLabel('样例 1 输入').fill('1 2')
  await page.getByLabel('样例 1 输出').fill('3')
  await page.getByRole('button', { name: '保存题面' }).click()
  await expect(page.getByText('题面已保存。')).toBeVisible()
  await page.getByLabel('测试输入').fill('10 20\n')
  await page.getByLabel('预期答案').fill('30\n')
  await page.getByRole('button', { name: '保存配对测试' }).click()
  await expect(page.getByText('测试点已保存。')).toBeVisible()
  const languages = await page
    .getByLabel('参考语言')
    .locator('option')
    .evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value))
  for (const language of languages) {
    await page.getByLabel('参考语言').selectOption(language)
    await page
      .getByLabel('参考程序')
      .fill(
        language === 'cpp17'
          ? '#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}'
          : 'print(sum(map(int, input().split())))',
      )
    const saved = page.waitForResponse(
      (response) =>
        response.request().method() === 'PUT' && response.url().endsWith('/references/' + language),
    )
    await page.getByRole('button', { name: '保存参考程序', exact: true }).click()
    expect((await saved).status()).toBe(200)
    await expect(page.getByText('参考程序已保存。')).toBeVisible()
  }
  await page.reload()
  await expect(page.getByLabel('题目标题')).toHaveValue('两数之和')
  const other = await context.newPage()
  await other.goto(page.url())
  await other.getByLabel('题目标题').fill('另一标签更新的两数之和')
  const changed = other.waitForResponse((r) => r.request().method() === 'PATCH')
  await other.getByRole('button', { name: '保存题面' }).click()
  expect((await changed).status()).toBe(200)
  await expect(other.getByText('题面已保存。')).toBeVisible()
  if (process.env.ASTRA_SERVER_PYTHON) {
    const conflict = page.waitForResponse(
      (r) => r.request().method() === 'POST' && r.url().endsWith('/preflight'),
    )
    await page.getByRole('button', { name: '启动预检' }).click()
    expect((await conflict).status()).toBe(409)
    await page.getByRole('button', { name: '重新读取修订，保留测试和参考程序输入' }).click()
    await expect(page.getByLabel('题目标题')).toHaveValue('另一标签更新的两数之和')
    await expect(page.getByRole('button', { name: '启动预检' })).toBeEnabled()
  } else {
    await page.reload()
    await expect(page.getByLabel('题目标题')).toHaveValue('另一标签更新的两数之和')
  }
  await other.close()
  await expect(page).toHaveTitle(/Astra/)
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({
    path: path.resolve('../../.local', `problem-sync-${testInfo.project.name}.png`),
    fullPage: true,
  })
  await page.getByRole('button', { name: '载入测试 1', exact: true }).click()
  await expect(page.getByLabel('测试输入')).toHaveValue('10 20\n')
  const preflight = page.waitForResponse(
    (response) => response.request().method() === 'POST' && response.url().endsWith('/preflight'),
  )
  await page.getByRole('button', { name: '启动预检' }).click()
  const preflightResponse = await preflight
  if (process.env.ASTRA_SERVER_PYTHON) {
    expect(preflightResponse.status()).toBe(202)
    await expect(page.getByText('预检状态：QUEUED')).toBeVisible()
  } else {
    // A standalone validation host deliberately does not implement B's routes.
    expect(preflightResponse.status()).toBe(404)
    await expect(page.getByRole('alert')).toBeVisible()
  }
  await page.getByRole('link', { name: '复制为新版本' }).click()
  await expect(page.getByLabel('题目标题')).toHaveValue('另一标签更新的两数之和')
  const copied = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith('/problem-versions'),
  )
  await page.getByRole('button', { name: '保存题面' }).click()
  expect((await copied).status()).toBe(201)
  await expect(page.getByText('题面已保存。')).toBeVisible()
  await page.getByRole('link', { name: '我的课程', exact: true }).click()
  await openCourse(page, course)
  await page.getByRole('link', { name: '管理题目' }).click()
  await page.getByRole('button', { name: '调整练习开放策略' }).click()
  await expect(page.getByLabel('题目家族编号')).not.toHaveValue('')
  await expect(page.getByLabel('开放版本')).toHaveValue('')
  await page.getByLabel('调整理由').fill('该题仍在备课，保持关闭练习开放')
  await page.getByRole('button', { name: '核对更改' }).click()
  await page.getByRole('button', { name: '确认调整', exact: true }).click()
  await expect(page.getByRole('button', { name: '调整练习开放策略' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
})
