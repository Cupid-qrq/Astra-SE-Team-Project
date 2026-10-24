import { useState } from 'react'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'

export function DialogHarness() {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)}>测试确认操作</button>
      <ConfirmDialog
        open={open}
        busy={busy}
        title="确认测试操作"
        description="仅供组件浏览器回归"
        confirmLabel="执行测试"
        onCancel={() => setOpen(false)}
        onConfirm={() => setBusy(true)}
      />
    </>
  )
}
