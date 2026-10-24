import { createRoot } from 'react-dom/client'
import { FixedHelp } from '../src/features/learning/FixedHelp'
import { api } from '../src/app/runtime'

export async function mountHelp() {
  const value = await api.feedbackVersion('d5e9d6a8-5cda-5f6d-9f43-d3610b4d57c6', 1)
  const host = document.createElement('div')
  document.querySelector('main')!.appendChild(host)
  createRoot(host).render(<FixedHelp state="FINISHED" verdict="WA" value={value} />)
}
