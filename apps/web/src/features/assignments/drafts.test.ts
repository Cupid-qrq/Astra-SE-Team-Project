import 'fake-indexeddb/auto'
import { afterEach, expect, it } from 'vitest'
import {
  activateDraftAccount,
  saveDraft,
  loadDraft,
  clearAccountDrafts,
  listAccountDrafts,
  rememberDraft,
  currentDraft,
  forgetDraftMemory,
} from './drafts'

const key = {
  userId: 'account-a',
  assignmentId: 'assignment',
  problemId: 'problem',
  language: 'python3' as const,
}
afterEach(async () => {
  await clearAccountDrafts('account-a')
  await clearAccountDrafts('account-b')
  forgetDraftMemory()
})
it('账户、作业、题目、语言均隔离，刷新后按原键恢复', async () => {
  activateDraftAccount('account-a')
  await saveDraft(key, 'print(1)')
  expect((await loadDraft(key))?.code).toBe('print(1)')
  expect(await loadDraft({ ...key, userId: 'account-b' })).toBeNull()
  expect(await loadDraft({ ...key, language: 'cpp17' })).toBeNull()
  expect(await loadDraft({ ...key, problemId: 'different' })).toBeNull()
  expect(await loadDraft({ ...key, assignmentId: 'different' })).toBeNull()
})
it('退出清理阻止迟到保存恢复旧账户草稿，重新登录后可新建', async () => {
  activateDraftAccount('account-a')
  const pending = saveDraft(key, 'late-write')
  await clearAccountDrafts('account-a')
  await pending
  await saveDraft(key, 'still-late')
  expect(await listAccountDrafts('account-a')).toEqual([])
  activateDraftAccount('account-a')
  await saveDraft(key, 'new-login')
  expect((await loadDraft(key))?.code).toBe('new-login')
})
it('会话过期保留内存，新账户不能看到前一账户代码', () => {
  activateDraftAccount('account-a')
  rememberDraft(key, 'unsaved-code')
  expect(currentDraft()?.code).toBe('unsaved-code')
  activateDraftAccount('account-b')
  expect(currentDraft()).toBeNull()
})
