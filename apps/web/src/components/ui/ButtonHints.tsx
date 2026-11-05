import { controlHint } from './controlHint'
import { useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'

const selector =
  'button, summary, a[href], [role="button"], [role="tab"], input[type="checkbox"], input[type="radio"], select'
type Hint = { button: HTMLElement; text: string; left: number; top: number; above: boolean }
type GeneratedTitle = { original: string | null; text: string }

function controlLabel(control: HTMLElement) {
  const labels = (control as HTMLInputElement).labels
  const labelText = labels
    ? [...labels]
        .map((label) => {
          const copy = label.cloneNode(true) as HTMLElement
          copy.querySelectorAll('input, select, textarea').forEach((field) => field.remove())
          return copy.textContent?.trim() || ''
        })
        .join(' ')
    : ''
  return (
    control.getAttribute('aria-label') || labelText || control.textContent?.trim() || '当前操作'
  )
}

export function ButtonHints() {
  const tooltipId = useId()
  const [hint, setHint] = useState<Hint | null>(null)
  useEffect(() => {
    if (!hint) return
    const control = hint.button
    const before = control.getAttribute('aria-describedby')
    control.setAttribute('aria-describedby', [before, tooltipId].filter(Boolean).join(' '))
    return () => {
      const remaining = (control.getAttribute('aria-describedby') || '')
        .split(/\s+/)
        .filter((value) => value && value !== tooltipId)
        .join(' ')
      if (remaining) control.setAttribute('aria-describedby', remaining)
      else control.removeAttribute('aria-describedby')
    }
  }, [hint, tooltipId])
  useEffect(() => {
    const titles = new Map<HTMLElement, GeneratedTitle>()
    let active: HTMLElement | null = null
    let closing: ReturnType<typeof setTimeout> | undefined
    const cancelClose = () => clearTimeout(closing)
    const close = () => {
      cancelClose()
      active = null
      setHint(null)
    }
    const closeSoon = () => {
      cancelClose()
      if (active && document.activeElement === active) return
      closing = setTimeout(close, 150)
    }
    function describe(control: HTMLElement) {
      const previous = titles.get(control)
      const current = control.getAttribute('title')
      const original = previous && current === previous.text ? previous.original : current
      const explicit = control.dataset.tooltip || original || undefined
      const label = controlLabel(control)
      const disabled =
        control.matches(':disabled') || control.getAttribute('aria-disabled') === 'true'
      const text = controlHint(label, {
        description:
          explicit ||
          (!disabled && control.matches('input[type="checkbox"], input[type="radio"]')
            ? `切换“${label}”选项。`
            : !disabled && control.matches('select')
              ? `选择“${label}”的选项。`
              : undefined),
        busy: control.getAttribute('aria-busy') === 'true',
        disabled,
        href: control.getAttribute('href') || undefined,
      })
      if (current !== text) {
        titles.set(control, { original, text })
        control.setAttribute('title', text)
      }
      return text
    }
    function restore(control: HTMLElement, generated: GeneratedTitle) {
      if (control.getAttribute('title') === generated.text) {
        if (generated.original === null) control.removeAttribute('title')
        else control.setAttribute('title', generated.original)
      }
      titles.delete(control)
    }
    function scan(element: Element) {
      const parent = element.closest<HTMLElement>(selector)
      if (parent) describe(parent)
      element.querySelectorAll<HTMLElement>(selector).forEach(describe)
    }
    function position(control: HTMLElement) {
      if (!control.isConnected) return close()
      const rect = control.getBoundingClientRect()
      if (rect.bottom < 0 || rect.top > window.innerHeight) {
        if (document.activeElement !== control) return close()
        active = control
        setHint(null)
        return
      }
      const width = Math.min(320, window.innerWidth - 24)
      const left = Math.max(
        width / 2 + 12,
        Math.min(window.innerWidth - width / 2 - 12, rect.left + rect.width / 2),
      )
      const above = window.innerHeight - rect.bottom < 100
      active = control
      setHint({
        button: control,
        text: describe(control),
        left,
        top: above ? rect.top - 8 : rect.bottom + 8,
        above,
      })
    }
    function show(event: Event) {
      if (!(event.target instanceof Element)) return
      cancelClose()
      if (event.target.closest('.button-tooltip')) return
      const control =
        event.target.closest<HTMLElement>(selector) ||
        event.target
          .closest('label')
          ?.querySelector<HTMLElement>('input[type="checkbox"], input[type="radio"], select')
      if (!control) return closeSoon()
      position(control)
    }
    function leave(event: PointerEvent) {
      const control = event.target instanceof Element ? event.target.closest(selector) : null
      if (control && event.relatedTarget instanceof Node && control.contains(event.relatedTarget))
        return
      closeSoon()
    }
    function key(event: KeyboardEvent) {
      if (event.key === 'Escape') close()
    }
    function scroll() {
      // Browser focus can scroll an off-screen link into view after focusin.
      if (active && document.activeElement === active) position(active)
      else close()
    }
    scan(document.body)
    const observer = new MutationObserver((records) => {
      for (const record of records) {
        if (record.target instanceof Element && record.target.closest('.cm-content')) continue
        const target =
          record.target instanceof Element ? record.target : record.target.parentElement
        if (target && !target.closest('.button-tooltip')) scan(target)
      }
      for (const [control, generated] of titles)
        if (!control.isConnected || !control.matches(selector)) restore(control, generated)
      if (active && (!active.isConnected || !active.matches(selector))) close()
      else if (active) position(active)
    })
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: [
        'title',
        'data-tooltip',
        'disabled',
        'aria-disabled',
        'aria-busy',
        'aria-label',
        'href',
        'role',
      ],
    })
    document.addEventListener('pointerover', show)
    document.addEventListener('pointerout', leave)
    document.addEventListener('focusin', show)
    document.addEventListener('focusout', close)
    document.addEventListener('pointerdown', close)
    document.addEventListener('click', close)
    document.addEventListener('keydown', key)
    window.addEventListener('scroll', scroll, true)
    window.addEventListener('resize', close)
    return () => {
      observer.disconnect()
      document.removeEventListener('pointerover', show)
      document.removeEventListener('pointerout', leave)
      document.removeEventListener('focusin', show)
      document.removeEventListener('focusout', close)
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('click', close)
      document.removeEventListener('keydown', key)
      window.removeEventListener('scroll', scroll, true)
      window.removeEventListener('resize', close)
      cancelClose()
      for (const [control, generated] of titles) restore(control, generated)
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
