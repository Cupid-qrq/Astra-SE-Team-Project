import { expect, test, type Page } from '@playwright/test'

async function openLearning(page: Page) {
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill('student_a')
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('link', { name: '我的学习', exact: true }).click()
}
test('正式应用：未连接提交源时，个人学习保留可访问的入口并显示不可用', async ({ page }) => {
  await openLearning(page)
  await expect(page.getByRole('heading', { name: '错题记录暂不可用' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '推荐练习暂不可用' })).toBeVisible()
  await page.getByLabel('提交类别').selectOption('PRACTICE')
  await expect(page.getByRole('heading', { name: '错题记录暂不可用' })).toBeVisible()
  await expect(page.getByRole('button', { name: '请求提示', exact: true })).toBeDisabled()
  await expect(page.getByRole('heading', { name: '提示历史' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
test('前端契约样例：错题来源、推荐链接和就绪提示的四段展示', async ({ page }) => {
  const id = '10000000-0000-4000-8000-000000000001'
  const hintId = '20000000-0000-4000-8000-000000000001'
  const time = '2026-10-01T00:00:00.000Z'
  await page.route('**/api/v1/review-items?**', (route) =>
    route.fulfill({
      json: {
        items:
          new URL(route.request().url()).searchParams.get('context') === 'FORMAL'
            ? [
                {
                  submission_id: id,
                  assignment_id: id,
                  problem_id: id,
                  title: '整数求和',
                  verdict: 'WA',
                  context: 'FORMAL',
                  accepted_at: time,
                },
              ]
            : [],
        next_cursor: null,
      },
    }),
  )
  await page.route('**/api/v1/recommendations', (route) =>
    route.fulfill({
      json: {
        items: [{ problem_id: id, practice_version_id: id, title: '下一道练习', tags: ['求和'] }],
      },
    }),
  )
  await page.route('**/api/v1/ai-hints', (route) =>
    route.fulfill(
      route.request().method() === 'GET'
        ? { json: { items: [{ hint_id: hintId, created_at: time }], next_cursor: null } }
        : { status: 202, json: { hint_id: hintId, status: 'PENDING' } },
    ),
  )
  await page.route('**/api/v1/ai-hints/' + hintId, (route) =>
    route.fulfill({
      json: {
        hint_id: hintId,
        submission_id: id,
        status: 'READY',
        reason_code: null,
        model_version: 'fixture',
        template_version_id: id,
        sections: {
          error_category: '算术错误',
          location_clues: '观察符号',
          checks: '手算样例',
          learning_advice: '复核表达式',
        },
        fallback_feedback: null,
        created_at: time,
      },
    }),
  )
  await openLearning(page)
  await expect(page.getByRole('link', { name: '下一道练习' })).toHaveAttribute(
    'href',
    `/practice-problems/${id}`,
  )
  await page.getByRole('link', { name: '为此提交请求提示' }).click()
  await expect(page.getByLabel('来源提交编号')).toHaveValue(id)
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: '请求提示', exact: true }).click()
  await expect(page.getByRole('region', { name: '提示详情' })).toContainText('建议需自行验证')
  for (const name of ['错误类别', '定位线索', '检查方向', '学习建议'])
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
  await page.getByLabel('提交类别').selectOption('PRACTICE')
  await expect(page.getByText('此类别暂无待复习的错题。')).toBeVisible()
})
