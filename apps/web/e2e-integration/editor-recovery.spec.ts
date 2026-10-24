import { expect, test, type Page } from '@playwright/test'

async function openEditor(page: Page) {
  await page.goto('/login')
  await page.getByLabel('账号', { exact: true }).fill('student_a')
  await page.getByLabel('密码', { exact: true }).fill('ExamplePassword123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('link', { name: '编辑器测试课程', exact: true }).click()
  await page.getByRole('link', { name: '编辑器固定作业', exact: true }).click()
  await page.getByRole('link', { name: '开始编程', exact: true }).click()
  await page.getByLabel('编程语言').selectOption('python3')
}
test('A编辑器端口：未知受理刷新后仍重放原始快照', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop', '交互恢复逻辑只跑桌面；基础流程另覆盖三个视口。')
  await openEditor(page)
  await page.getByRole('textbox', { name: '代码编辑器' }).fill('print(10)')
  // Explicit B-port fake, separate from real HTTP/PostgreSQL teaching services.
  await page.evaluate(async () => {
    const path = '/src/features/integrations/teaching.ts'
    const { teaching } = await import(path)
    teaching.submissions.send = async () => {
      throw new Error('TEST_UNKNOWN_ACCEPTANCE')
    }
  })
  await page.getByRole('button', { name: '提交代码', exact: true }).click()
  await expect(page.getByRole('button', { name: '核对上次提交', exact: true })).toBeVisible()
  const before = await page.evaluate(async () => {
    const path = '/src/features/assignments/drafts.ts'
    return (await import(path)).currentDraft().pending
  })
  await page.getByRole('textbox', { name: '代码编辑器' }).fill('print(20)')
  await expect(page.getByText(/已保存于/)).toBeVisible()
  await page.reload()
  await page.getByLabel('编程语言').selectOption('python3')
  await expect(page.getByRole('textbox', { name: '代码编辑器' })).toHaveText('print(20)')
  await page.evaluate(async () => {
    const path = '/src/features/integrations/teaching.ts'
    const { teaching } = await import(path)
    teaching.submissions.send = async (intent: unknown) => {
      sessionStorage.setItem('test.replayed', JSON.stringify(intent))
      return {
        submission_id: 'test-receipt',
        mode: 'FORMAL',
        accepted_at: '2026-10-25T00:00:00.000Z',
      }
    }
  })
  await page.getByRole('button', { name: '核对上次提交', exact: true }).click()
  await expect(page.getByText(/提交已受理，编号 test-receipt/)).toBeVisible()
  expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem('test.replayed')!))).toEqual(
    before,
  )
  expect(before.code).toBe('print(10)')
  await expect(page.getByRole('textbox', { name: '代码编辑器' })).toHaveText('print(20)')
})

test('真实会话失效时仍可复制当前代码', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop', '会话恢复逻辑只跑桌面。')
  await page.clock.install()
  await openEditor(page)
  await page.getByRole('textbox', { name: '代码编辑器' }).fill('print("preserve")')
  await expect(page.getByText(/已保存于/)).toBeVisible()
  const session = await (await page.request.get('/api/v1/auth/session')).json()
  expect(
    (
      await page.request.post('/api/v1/auth/logout', {
        headers: { Origin: 'https://localhost:4175', 'X-CSRF-Token': session.csrf_token },
      })
    ).status(),
  ).toBe(204)
  await page.clock.fastForward(31_000)
  await expect(page.getByRole('heading', { name: '会话已失效' })).toBeVisible()
  await expect(page.getByLabel('保留的代码')).toHaveValue('print("preserve")')
})

test('未知正式提交经确定拒绝后可主动切换练习且保留代码', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop', '拒绝恢复逻辑只跑桌面。')
  await openEditor(page)
  await page.getByRole('textbox', { name: '代码编辑器' }).fill('print(30)')
  await page.evaluate(async () => {
    const { teaching } = await import('/src/features/integrations/teaching.ts')
    const { ApiError } = await import('/src/lib/api/client.ts')
    let count = 0
    teaching.submissions.send = async () => {
      count += 1
      throw count === 1
        ? new ApiError(0, 'NETWORK_ERROR', '测试断线')
        : new ApiError(409, 'SUBMISSION_INTENT_MISMATCH', '正式提交已截止')
    }
  })
  await page.getByRole('button', { name: '提交代码', exact: true }).click()
  await expect(page.getByLabel('提交意图')).toBeDisabled()
  await page.getByRole('button', { name: '核对上次提交', exact: true }).click()
  await expect(page.getByLabel('提交意图')).toBeEnabled()
  await page.getByLabel('提交意图').selectOption('PRACTICE')
  await expect(page.getByRole('textbox', { name: '代码编辑器' })).toHaveText('print(30)')
  await expect(page.getByRole('button', { name: '提交代码', exact: true })).toBeVisible()
})
