import { expect, type Page } from '@playwright/test'

// Courses are ordered by server IDs; a newly created course can be on a later page.
export async function openCourse(page: Page, title: string) {
  await expect(page.getByRole('table', { name: '我的课程', exact: true })).toBeVisible()
  const link = page.getByRole('link', { name: title, exact: true })
  const more = page.getByRole('button', { name: '加载更多课程', exact: true })
  while (!(await link.count()) && (await more.count())) {
    const footer = page.locator('.table-footnote')
    const previous = await footer.textContent()
    await more.click()
    await expect(footer).not.toHaveText(previous!)
  }
  await link.click()
}
