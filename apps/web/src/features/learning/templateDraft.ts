import type { components } from '../../lib/api/schema'
export type Fields = components['schemas']['TemplateDraft']
type Placeholder = Fields['allowed_placeholders'][number]
export const examples: Record<Placeholder, string> = {
  public_problem: '读取两个整数，输出它们的和。',
  public_samples: '输入 2 3，输出 5',
  student_code: 'print(a - b)',
  sanitized_diagnostic: '公开样例输出不匹配',
  verdict: 'WA',
  question: '我应该先检查哪个运算？',
}
export const names = Object.keys(examples) as Placeholder[]
export function inspectTemplate(fields: Fields) {
  let invalidPlaceholder = false
  const remainder = fields.body.replace(/\{([a-z_]+)\}/g, (_, name: string) => {
    if (!fields.allowed_placeholders.includes(name as Placeholder)) invalidPlaceholder = true
    return ''
  })
  const bytes = new TextEncoder().encode(fields.body).length
  const error = !fields.body.trim()
    ? '请填写给 AI 的指导要求。'
    : bytes > 8192
      ? '给 AI 的指导要求超过 8192 字节。'
      : invalidPlaceholder || /[{}]/.test(remainder)
        ? '请检查花括号，并勾选正文使用的每个占位符。'
        : !fields.schema_version.trim() || [...fields.schema_version].length > 40
          ? '请填写有效的回复格式版本。'
          : ''
  const preview = fields.body.replace(/\{([a-z_]+)\}/g, (token, name: string) =>
    fields.allowed_placeholders.includes(name as Placeholder)
      ? examples[name as Placeholder]
      : token,
  )
  return { bytes, error, preview }
}
type Snapshot = { revision: number; fields: Fields }
export function readSnapshot(key: string): Snapshot | null {
  try {
    const raw = sessionStorage.getItem(key)
    if (!raw || raw.length > 64000) return null
    const value = JSON.parse(raw) as Snapshot
    const fields = value.fields
    return Number.isSafeInteger(value.revision) &&
      value.revision >= 1 &&
      typeof fields.body === 'string' &&
      typeof fields.schema_version === 'string' &&
      Array.isArray(fields.allowed_placeholders) &&
      fields.allowed_placeholders.every((name) => names.includes(name))
      ? value
      : null
  } catch {
    return null
  }
}
export function storeSnapshot(key: string, value: Snapshot | null) {
  try {
    if (value) sessionStorage.setItem(key, JSON.stringify(value))
    else sessionStorage.removeItem(key)
    return true
  } catch {
    return false
  }
}
