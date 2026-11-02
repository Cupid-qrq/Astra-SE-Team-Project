export type HelpFields = { title: string; explanation: string; checklistText: string }
export type HelpSnapshot = { revision: number; fields: HelpFields }

function key(ownerId: string, catalogId: string) {
  return `astra:feedback:${ownerId}:${catalogId}`
}
export function readHelpDraft(ownerId: string, catalogId: string): HelpSnapshot | null {
  try {
    const raw = sessionStorage.getItem(key(ownerId, catalogId))
    if (!raw || raw.length > 32768) return null
    const value = JSON.parse(raw) as HelpSnapshot
    if (!Number.isSafeInteger(value.revision) || value.revision < 1 || !value.fields) return null
    if (
      ![value.fields.title, value.fields.explanation, value.fields.checklistText].every(
        (v) => typeof v === 'string',
      )
    )
      return null
    return value
  } catch {
    return null
  }
}
export function writeHelpDraft(ownerId: string, catalogId: string, value: HelpSnapshot | null) {
  try {
    if (value) sessionStorage.setItem(key(ownerId, catalogId), JSON.stringify(value))
    else sessionStorage.removeItem(key(ownerId, catalogId))
    return true
  } catch {
    return false
  }
}
