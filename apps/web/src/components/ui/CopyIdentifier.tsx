import { useState } from 'react'
import { Button } from './Button'
import './help-identifiers.css'

export function CopyIdentifier({ label, value }: { label: string; value: string }) {
  const [message, setMessage] = useState('')
  async function copy() {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable')
      await navigator.clipboard.writeText(value)
      setMessage('已复制')
    } catch {
      setMessage('复制未获允许，请选中编号手动复制。')
    }
  }
  return (
    <div className="copy-identifier">
      <span className="identifier-label">{label}</span>
      <code>{value}</code>
      <Button variant="quiet" title={`复制完整${label}`} onClick={() => void copy()}>
        复制{label}
      </Button>
      <span className="identifier-status" role="status">
        {message}
      </span>
    </div>
  )
}
