import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Button } from './Button'
type Props = {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  onCancel: () => void
  onConfirm: () => void
  busy?: boolean
  children?: ReactNode
}
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  onCancel,
  onConfirm,
  busy = false,
  children,
}: Props) {
  const titleId = useId()
  const descriptionId = useId()
  const dialog = useRef<HTMLDivElement>(null)
  const backdrop = useRef<HTMLDivElement>(null)
  const cancel = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const siblings = [...document.body.children].filter(
      (element): element is HTMLElement =>
        element instanceof HTMLElement && element !== backdrop.current,
    )
    const inertStates = siblings.map((element) => element.inert)
    siblings.forEach((element) => {
      element.inert = true
    })
    function containFocus(event: FocusEvent) {
      if (dialog.current && !dialog.current.contains(event.target as Node)) {
        const target =
          dialog.current.querySelector<HTMLElement>('button:not(:disabled)') || dialog.current
        target.focus()
      }
    }
    document.addEventListener('focusin', containFocus)
    cancel.current?.focus()
    return () => {
      document.removeEventListener('focusin', containFocus)
      siblings.forEach((element, index) => {
        element.inert = inertStates[index]
      })
      document.body.style.overflow = overflow
      previous?.focus()
    }
  }, [open])
  useEffect(() => {
    if (open && busy) dialog.current?.focus()
    if (open && !busy && document.activeElement === dialog.current) cancel.current?.focus()
  }, [open, busy])
  if (!open) return null
  return createPortal(
    <div className="dialog-backdrop" ref={backdrop}>
      <div
        ref={dialog}
        className="dialog"
        role="dialog"
        tabIndex={-1}
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && !busy) {
            event.preventDefault()
            onCancel()
          }
          if (event.key === 'Tab') {
            const elements = dialog.current?.querySelectorAll<HTMLElement>(
              'button:not(:disabled), input:not(:disabled), [tabindex="0"]',
            )
            if (!elements?.length) {
              event.preventDefault()
              return
            }
            const first = elements[0],
              last = elements[elements.length - 1]
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault()
              last.focus()
            }
            if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault()
              first.focus()
            }
          }
        }}
      >
        <h2 id={titleId}>{title}</h2>
        <p id={descriptionId}>{description}</p>
        {children}
        <div className="dialog-actions">
          <button
            ref={cancel}
            type="button"
            className="button button--secondary"
            disabled={busy}
            onClick={onCancel}
          >
            取消
          </button>
          <Button busy={busy} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
