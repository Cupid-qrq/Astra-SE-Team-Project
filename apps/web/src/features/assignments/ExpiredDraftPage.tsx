import { Link } from 'react-router-dom'
import { currentDraft, downloadText } from './drafts'
import { Button } from '../../components/ui/Button'
import { TextArea } from '../../components/ui/TextArea'
export function ExpiredDraftPage() {
  const draft = currentDraft()
  return (
    <main className="main-content">
      <h1>会话已失效</h1>
      <p>当前代码仍保留在这里。可复制或导出，再登录原账户继续。</p>
      {draft && (
        <>
          <TextArea label="保留的代码" value={draft.code} readOnly rows={18} />
          <Button
            onClick={() =>
              downloadText(`astra-draft.${draft.language === 'python3' ? 'py' : 'cpp'}`, draft.code)
            }
          >
            导出当前代码
          </Button>
        </>
      )}
      <p>
        <Link to="/login">重新登录</Link>
      </p>
    </main>
  )
}
