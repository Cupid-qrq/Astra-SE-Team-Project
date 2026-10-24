import { SafeMarkdown } from '../../components/ui/SafeMarkdown'
import type { components } from '../../lib/api/schema'

export type FeedbackVersion = components['schemas']['FeedbackVersion']
export type FixedHelpProps = {
  state: string
  verdict: string | null
  value?: FeedbackVersion
  loading?: boolean
  error?: string
}

/** B's result panel supplies the current attempt's frozen version, never a draft/latest lookup. */
export function FixedHelp({ state, verdict, value, loading, error }: FixedHelpProps) {
  if (state !== 'FINISHED') return <p className="muted">评测完成后可查看对应的固定帮助。</p>
  if (!verdict || !['CE', 'WA', 'TLE', 'RE', 'SE'].includes(verdict)) return null
  return (
    <section className="panel stack" aria-label="固定帮助">
      {verdict === 'SE' && <p className="notice">平台故障不代表代码错误，请关注教师或平台通知。</p>}
      {loading ? (
        <p role="status">正在读取本轮评测的固定帮助…</p>
      ) : error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : value ? (
        <>
          <h3>{value.title}</h3>
          <SafeMarkdown>{value.explanation}</SafeMarkdown>
          <ul>
            {value.checklist.map((item, index) => (
              <li key={index}>
                <SafeMarkdown>{item}</SafeMarkdown>
              </li>
            ))}
          </ul>
          <p className="muted">固定帮助 · 版本 {value.feedback_version_id}</p>
        </>
      ) : (
        <p role="status">本轮帮助暂不可用，请稍后重试。</p>
      )}
    </section>
  )
}
