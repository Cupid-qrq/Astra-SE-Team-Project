import { controlHint } from './controlHint'
import { useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'

type Hint = { button: HTMLElement; text: string; left: number; top: number; above: boolean }

export function ButtonHints() {
  const tooltipId = useId()
  const [hint, setHint] = useState<Hint | null>(null)
  useEffect(() => {
    if (!hint) return
    const control = hint.button
    const before = control.getAttribute('aria-describedby')
    const observer = new MutationObserver(() => {
      if (!control.isConnected) setHint(null)
    })
    observer.observe(document.body, { childList: true, subtree: true })
    control.setAttribute('aria-describedby', [before, tooltipId].filter(Boolean).join(' '))
    return () => {
      observer.disconnect()
      const remaining = (control.getAttribute('aria-describedby') || '')
        .split(/\s+/)
        .filter((value) => value && value !== tooltipId)
        .join(' ')
      if (remaining) control.setAttribute('aria-describedby', remaining)
      else control.removeAttribute('aria-describedby')
    }
  }, [hint, tooltipId])
  useEffect(() => {
    let closing: ReturnType<typeof setTimeout> | undefined
    const cancelClose = () => clearTimeout(closing)
    const close = () => {
      cancelClose()
      setHint(null)
    }
    const closeSoon = () => {
      cancelClose()
      closing = setTimeout(close, 150)
    }
    function show(event: Event) {
      if (!(event.target instanceof Element)) return
      cancelClose()
      if (event.target.closest('.button-tooltip')) return
      const selector =
        'button, summary, a[href], [role="button"], [role="tab"], input[type="checkbox"], input[type="radio"], select'
      const button =
        event.target.closest<HTMLElement>(selector) ||
        event.target
          .closest('label')
          ?.querySelector<HTMLElement>('input[type="checkbox"], input[type="radio"], select')
      if (!button) return closeSoon()
      const explicit = button.dataset.tooltip || button.title || undefined
      const labels = (button as HTMLInputElement).labels
      const labelText = labels
        ? [...labels]
            .map((label) => {
              const copy = label.cloneNode(true) as HTMLElement
              copy
                .querySelectorAll('input, select, textarea')
                .forEach((control) => control.remove())
              return copy.textContent?.trim() || ''
            })
            .join(' ')
        : ''
      const label =
        button.getAttribute('aria-label') || labelText || button.textContent?.trim() || '当前操作'
      const disabled =
        button.matches(':disabled') || button.getAttribute('aria-disabled') === 'true'
      const text = controlHint(label, {
        description:
          explicit ||
          (!disabled && button.matches('input[type="checkbox"], input[type="radio"]')
            ? `切换“${label}”选项。`
            : !disabled && button.matches('select')
              ? `选择“${label}”的选项。`
              : undefined),
        busy: button.getAttribute('aria-busy') === 'true',
        disabled,
      })
      if (!text) return close()
      const rect = button.getBoundingClientRect()
      const width = Math.min(320, window.innerWidth - 24)
      const left = Math.max(
        width / 2 + 12,
        Math.min(window.innerWidth - width / 2 - 12, rect.left + rect.width / 2),
      )
      const above = window.innerHeight - rect.bottom < 100
      setHint({ button, text, left, top: above ? rect.top - 8 : rect.bottom + 8, above })
    }
    function leave(event: PointerEvent) {
      const button =
        event.target instanceof Element
          ? event.target.closest(
              'button, summary, a[href], [role="button"], [role="tab"], input[type="checkbox"], input[type="radio"], select',
            )
          : null
      if (button && event.relatedTarget instanceof Node && button.contains(event.relatedTarget))
        return
      closeSoon()
    }
    function key(event: KeyboardEvent) {
      if (event.key === 'Escape') close()
    }
    document.addEventListener('pointerover', show)
    document.addEventListener('pointerout', leave)
    document.addEventListener('focusin', show)
    document.addEventListener('focusout', close)
    document.addEventListener('pointerdown', close)
    document.addEventListener('click', close)
    document.addEventListener('keydown', key)
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      document.removeEventListener('pointerover', show)
      document.removeEventListener('pointerout', leave)
      document.removeEventListener('focusin', show)
      document.removeEventListener('focusout', close)
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('click', close)
      cancelClose()
      document.removeEventListener('keydown', key)
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [])
  if (!hint || !hint.button.isConnected) return null
  return createPortal(
    <div
      id={tooltipId}
      role="tooltip"
      className="button-tooltip"
      style={{
        left: hint.left,
        top: hint.top,
        transform: hint.above ? 'translate(-50%, -100%)' : 'translateX(-50%)',
      }}
    >
      {hint.text}
    </div>,
    hint.button.closest('dialog[open]') || document.body,
  )
}
