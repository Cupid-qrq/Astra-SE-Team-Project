import { useId, type InputHTMLAttributes } from 'react'
type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  error?: string
  hint?: string
}
export function Field({ label, error, hint, id, ...props }: Props) {
  const generated = useId()
  const inputId = id || generated
  const description = error || hint
  return (
    <div className="field">
      <label htmlFor={inputId}>{label}</label>
      <input
        {...props}
        id={inputId}
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
