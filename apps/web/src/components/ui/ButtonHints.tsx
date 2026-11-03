import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

type Hint = { button: HTMLButtonElement; text: string; left: number; top: number; above: boolean }

export function ButtonHints() {
  const [hint, setHint] = useState<Hint | null>(null)
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
      const button = event.target.closest('button')
      if (!button) return closeSoon()
      const text =
        button.dataset.tooltip ||
        button.title ||
        button.getAttribute('aria-label') ||
        button.textContent?.trim()
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
      const button = event.target instanceof Element ? event.target.closest('button') : null
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
