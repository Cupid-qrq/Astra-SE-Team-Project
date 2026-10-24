import { AlertCircle, Inbox, LoaderCircle, ShieldAlert } from 'lucide-react'
import { Button } from './Button'
type Props = {
  kind: 'loading' | 'empty' | 'error' | 'forbidden'
  title: string
  description?: string
  onRetry?: () => void
}
export function StatePanel({ kind, title, description, onRetry }: Props) {
  const Icon = { loading: LoaderCircle, empty: Inbox, error: AlertCircle, forbidden: ShieldAlert }[
    kind
  ]
  return (
    <section
      className={`state-panel state-panel--${kind}`}
      role={kind === 'error' ? 'alert' : 'status'}
      aria-live="polite"
    >
      <Icon size={28} aria-hidden="true" />
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          重试
        </Button>
      )}
    </section>
  )
}
