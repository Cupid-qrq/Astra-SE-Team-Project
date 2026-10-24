import type { SubmissionIntent } from '../integrations/teaching'
export type DraftKey = {
  userId: string
  assignmentId: string
  problemId: string
  language: 'cpp17' | 'python3'
}
export type Draft = DraftKey & {
  key: string
  code: string
  updatedAt: string
  pending?: SubmissionIntent
}
let database: Promise<IDBDatabase> | undefined
let memory: Draft | null = null
const blocked = new Set<string>()
const generations = new Map<string, number>()
const keyOf = (key: DraftKey) =>
  JSON.stringify([key.userId, key.assignmentId, key.problemId, key.language])

function db() {
  database ??= new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open('astra.drafts', 1)
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore('drafts', { keyPath: 'key' })
      store.createIndex('userId', 'userId')
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => {
      database = undefined
      reject(new Error('本机草稿存储不可用。'))
    }
  })
  return database
}
function finished(tx: IDBTransaction) {
  return new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve()
    tx.onabort = tx.onerror = () => reject(new Error('本机草稿保存失败，请复制或导出代码。'))
  })
}
export function activateDraftAccount(userId: string) {
  blocked.delete(userId)
  if (memory && memory.userId !== userId) memory = null
}
export function rememberDraft(key: DraftKey, code: string, pending?: SubmissionIntent) {
  if (!blocked.has(key.userId))
    memory = {
      ...key,
      key: keyOf(key),
      code,
      updatedAt: new Date().toISOString(),
      ...(pending ? { pending } : {}),
    }
}
export const currentDraft = () => memory
export function forgetDraftMemory() {
  memory = null
}
export async function saveDraft(
  key: DraftKey,
  code: string,
  pending?: SubmissionIntent,
): Promise<string | null> {
  const generation = generations.get(key.userId) || 0
  if (blocked.has(key.userId)) return null
  const connection = await db()
  if (blocked.has(key.userId) || generation !== (generations.get(key.userId) || 0)) return null
  const updatedAt = new Date().toISOString()
  const tx = connection.transaction('drafts', 'readwrite')
  tx.objectStore('drafts').put({
    ...key,
    key: keyOf(key),
    code,
    updatedAt,
    ...(pending ? { pending } : {}),
  } satisfies Draft)
  await finished(tx)
  return updatedAt
}
export async function loadDraft(key: DraftKey): Promise<Draft | null> {
  const connection = await db()
  const tx = connection.transaction('drafts', 'readonly')
  return new Promise((resolve, reject) => {
    const request = tx.objectStore('drafts').get(keyOf(key))
    request.onsuccess = () => resolve(request.result || null)
    request.onerror = () => reject(new Error('无法读取本机草稿。'))
  })
}
export async function listAccountDrafts(userId: string): Promise<Draft[]> {
  const connection = await db()
  const tx = connection.transaction('drafts', 'readonly')
  return new Promise((resolve, reject) => {
    const request = tx.objectStore('drafts').index('userId').getAll(userId)
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(new Error('无法读取本账户草稿。'))
  })
}
export async function clearAccountDrafts(userId: string): Promise<void> {
  blocked.add(userId)
  generations.set(userId, (generations.get(userId) || 0) + 1)
  if (memory?.userId === userId) memory = null
  const connection = await db()
  const tx = connection.transaction('drafts', 'readwrite')
  const request = tx.objectStore('drafts').index('userId').openCursor(IDBKeyRange.only(userId))
  request.onsuccess = () => {
    const cursor = request.result
    if (cursor) {
      cursor.delete()
      cursor.continue()
    }
  }
  await finished(tx)
}
export function downloadText(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
