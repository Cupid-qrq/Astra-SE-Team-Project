import { controlHint } from './controlHint'
import { Children, type ButtonHTMLAttributes } from 'react'
type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  busy?: boolean
  variant?: 'primary' | 'secondary' | 'quiet' | 'danger'
}
export function Button({
  busy = false,
  variant = 'primary',
  className = '',
  disabled,
  title,
  children,
  type = 'button',
  ...props
}: Props) {
  const label =
    props['aria-label'] ||
    Children.toArray(children)
      .filter((child) => typeof child === 'string' || typeof child === 'number')
      .join('') ||
    '执行此操作。'
  const description = controlHint(label, { busy, disabled, description: title })
  return (
    <button
      {...props}
      type={type}
      data-tooltip={description}
      aria-description={description}
      className={`button button--${variant} ${className}`}
      disabled={disabled || busy}
      aria-busy={busy}
    >
      {children}
    </button>
  )
}
