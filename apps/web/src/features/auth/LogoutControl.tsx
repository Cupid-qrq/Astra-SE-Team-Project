import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { api, clearSession } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import {
  listAccountDrafts,
  currentDraft,
  clearAccountDrafts,
  forgetDraftMemory,
  downloadText,
  type Draft,
} from '../assignments/drafts'

export function LogoutControl({ userId }: { userId: string }) {
  const [drafts, setDrafts] = useState<Draft[] | null>(null)
  const [reading, setReading] = useState(false)
  const [error, setError] = useState('')
  const logout = useMutation({
    mutationFn: async () => {
      await api.logout()
      try {
        await clearAccountDrafts(userId)
        sessionStorage.removeItem('astra.draftCleanupWarning')
      } catch {
        sessionStorage.setItem(
          'astra.draftCleanupWarning',
          '已退出登录，但本机草稿清理失败。请在共享设备上清除此站点的数据。',
        )
      }
      forgetDraftMemory()
      clearSession()
    },
  })
  async function prepare() {
    setReading(true)
    try {
      const values = new Map((await listAccountDrafts(userId)).map((d) => [d.key, d]))
      const memory = currentDraft()
      if (memory?.userId === userId) values.set(memory.key, memory)
      if (values.size) setDrafts([...values.values()])
      else logout.mutate()
    } catch (e) {
      setError((e as Error).message)
      setDrafts(currentDraft()?.userId === userId ? [currentDraft()!] : [])
    } finally {
      setReading(false)
    }
  }
  return (
    <>
      <Button
        variant="quiet"
        aria-label="退出登录"
        title="退出登录"
        busy={reading || logout.isPending}
        onClick={() => void prepare()}
      >
        <LogOut size={18} aria-hidden="true" />
      </Button>
      {logout.error && !drafts && (
        <p role="alert" className="form-error">
          {logout.error.message}
        </p>
      )}
      <ConfirmDialog
        open={drafts !== null}
        title="退出前保存草稿"
        description={`${drafts?.length || 0} 份本账户草稿将从本机清除，可先导出备份。${error || logout.error?.message || ''}`}
        confirmLabel="退出并清除草稿"
        onCancel={() => setDrafts(null)}
        onConfirm={() => logout.mutate()}
        busy={logout.isPending}
      >
        <Button
          variant="secondary"
          disabled={logout.isPending}
          onClick={() => downloadText('astra-drafts.json', JSON.stringify(drafts, null, 2))}
        >
          导出本账户草稿
        </Button>
      </ConfirmDialog>
    </>
  )
}
