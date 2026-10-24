import { createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { DialogHarness } from './dialog-harness'
export function mount(container: HTMLElement) {
  createRoot(container).render(createElement(DialogHarness))
}
