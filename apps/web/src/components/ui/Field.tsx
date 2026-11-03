import { useId, type InputHTMLAttributes } from 'react'
type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  error?: string
  hint?: string
}
export function Field({ label, error, hint, id, placeholder, ...props }: Props) {
  const generated = useId()
  const inputId = id || generated
  const identifier = label.includes('编号') && (!props.type || props.type === 'text')
  const example = '00000000-0000-4000-8000-000000000001'
  const description =
    error ||
    hint ||
    (identifier ? '示例仅展示编号格式，请从对应记录列表或操作结果复制实际编号。' : undefined)
  return (
    <div className="field">
      <label htmlFor={inputId}>{label}</label>
      <input
        {...props}
        id={inputId}
        placeholder={placeholder ?? (identifier ? `格式示例 ${example}` : undefined)}
        aria-invalid={error ? true : undefined}
        aria-describedby={description ? `${inputId}-help` : undefined}
      />
      {description && (
        <p id={`${inputId}-help`} className={error ? 'field-error' : 'field-hint'}>
          {description}
        </p>
      )}
    </div>
  )
}
