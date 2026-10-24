import type { ButtonHTMLAttributes } from 'react'
type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  busy?: boolean
  variant?: 'primary' | 'secondary' | 'quiet' | 'danger'
}
export function Button({
  busy = false,
  variant = 'primary',
  className = '',
  disabled,
  children,
  type = 'button',
  ...props
}: Props) {
  return (
    <button
      {...props}
      type={type}
      className={`button button--${variant} ${className}`}
      disabled={disabled || busy}
      aria-busy={busy}
    >
      {children}
    </button>
  )
}
