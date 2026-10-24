import { lazy, Suspense, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api, sessionKey } from '../../app/runtime'
import { ApiError } from '../../lib/api/client'
import type { components } from '../../lib/api/schema'
import { Button } from '../../components/ui/Button'
import { StatePanel } from '../../components/ui/StatePanel'
import { SafeMarkdown } from '../../components/ui/SafeMarkdown'
import { TextArea } from '../../components/ui/TextArea'
import { beijingTime } from './time'
import {
  currentDraft,
  downloadText,
  loadDraft,
  rememberDraft,
  saveDraft,
  type Draft,
  type DraftKey,
} from './drafts'
import {
  createSubmissionAttempt,
  restoreSubmissionAttempt,
  type SubmissionAttempt,
} from './submission'
import { teaching, type SubmissionReceipt } from '../integrations/teaching'

const CodeEditor = lazy(() => import('./CodeEditor'))
type Schema = components['schemas']
const subscribeViewport = (callback: () => void) => {
  window.addEventListener('resize', callback)
  return () => window.removeEventListener('resize', callback)
}

export function EditorPage() {
  const { id = '', problemId = '' } = useParams()
  const session = useQuery({ queryKey: sessionKey, queryFn: api.session })
  const assignment = useQuery({
    queryKey: ['assignment', id],
    queryFn: () => api.assignment(id),
    refetchInterval: 30_000,
  })
  const problem = useQuery({
    queryKey: ['assignment-problem', id, problemId],
    queryFn: () => api.assignmentProblem(id, problemId),
  })
  if (assignment.isError || problem.isError)
    return (
      <StatePanel
        kind="error"
        title="编程工作区不可用"
        description={(assignment.error || problem.error)?.message}
        onRetry={() => {
          void assignment.refetch()
          void problem.refetch()
        }}
      />
    )
  if (!session.data?.user || assignment.isPending || problem.isPending)
    return <StatePanel kind="loading" title="正在准备编程工作区…" />
  return (
    <EditorWorkspace
      key={`${session.data.user.user_id}:${id}:${problemId}`}
      user={session.data.user}
      assignment={assignment.data}
      problem={problem.data}
    />
  )
}
function EditorWorkspace({
  user,
  assignment,
  problem,
}: {
  user: Schema['User']
  assignment: Schema['AssignmentView']
  problem: Schema['PublicProblem']
}) {
  const [language, setLanguage] = useState(problem.profile.languages[0].language_key)
  const [tab, setTab] = useState<'problem' | 'code'>('problem')
  const [split, setSplit] = useState(() => {
    try {
      return Math.min(65, Math.max(30, Number(localStorage.getItem('astra.editor.split')) || 42))
    } catch {
      return 42
    }
  })
  const width = useSyncExternalStore(subscribeViewport, () => window.innerWidth)
  const phone = width < 600
  const layout = useRef<HTMLDivElement>(null)
  function resize(value: number) {
    const next = Math.min(65, Math.max(30, value))
    setSplit(next)
    try {
      localStorage.setItem('astra.editor.split', String(next))
    } catch {
      /* layout preference is optional */
    }
  }
  const key: DraftKey = useMemo(
    () => ({
      userId: user.user_id,
      assignmentId: assignment.assignment_id,
      problemId: problem.problem_id,
      language,
    }),
    [user.user_id, assignment.assignment_id, problem.problem_id, language],
  )
  return (
    <>
      <Link className="back-link" to={`/assignments/${assignment.assignment_id}`}>
        ← {assignment.title}
      </Link>
      <header className="page-heading">
        <div>
          <h1>{problem.title}</h1>
          <p>截止 {beijingTime(assignment.due_at)}（北京时间）</p>
        </div>
        <span className="status-label">
          {assignment.state === 'OPEN'
            ? '作业进行中'
            : assignment.state === 'CLOSED'
              ? '已截止 · 可练习'
              : '只读预览'}
        </span>
      </header>
      <div className="editor-tabs" role="tablist" aria-label="编程工作区视图">
        <button role="tab" aria-selected={tab === 'problem'} onClick={() => setTab('problem')}>
          题目
        </button>
        <button role="tab" aria-selected={tab === 'code'} onClick={() => setTab('code')}>
          代码
        </button>
      </div>
      <div
        ref={layout}
        className={`editor-workspace editor-tab-${tab}`}
        style={{ gridTemplateColumns: `${split}fr 8px ${100 - split}fr` }}
      >
        <section className="problem-pane" aria-label="题目说明">
          <SafeMarkdown>{problem.statement}</SafeMarkdown>
          <h2>公开样例</h2>
          {problem.samples.map((s, i) => (
            <div key={i}>
              <h3>样例 {i + 1}</h3>
              <p>输入</p>
              <pre>{s.input}</pre>
              <p>输出</p>
              <pre>{s.output}</pre>
            </div>
          ))}
          <h2>运行限制</h2>
          <p>
            内存 {problem.profile.memory_bytes / 1048576} MiB · 输出{' '}
            {problem.profile.output_bytes / 1048576} MiB
          </p>
          {problem.profile.languages.map((l) => (
            <p key={l.language_key}>
              {l.language_key} · {l.version} · CPU {l.cpu_time_ms / 1000} 秒 · 总时限{' '}
              {l.wall_time_ms / 1000} 秒
            </p>
          ))}
        </section>
        <div
          className="editor-divider"
          role="separator"
          tabIndex={0}
          aria-label="调整题面宽度"
          aria-orientation="vertical"
          aria-valuemin={30}
          aria-valuemax={65}
          aria-valuenow={Math.round(split)}
          onKeyDown={(e) => {
            if (['ArrowLeft', 'ArrowRight'].includes(e.key)) {
              e.preventDefault()
              resize(split + (e.key === 'ArrowLeft' ? -2 : 2))
            }
          }}
          onPointerDown={(e) => e.currentTarget.setPointerCapture(e.pointerId)}
          onPointerMove={(e) => {
            if (e.currentTarget.hasPointerCapture(e.pointerId) && layout.current) {
              const rect = layout.current.getBoundingClientRect()
              resize(((e.clientX - rect.left) / rect.width) * 100)
            }
          }}
        />
        <section className="code-pane" aria-label="代码工作区">
          <label className="field">
            编程语言
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as 'cpp17' | 'python3')}
            >
              {problem.profile.languages.map((l) => (
                <option key={l.language_key} value={l.language_key}>
                  {l.language_key} · {l.version}
                </option>
              ))}
            </select>
          </label>
          {phone && <p>手机端仅支持阅读题目和草稿，请在电脑上编程。</p>}
          <DraftLoader
            key={JSON.stringify(key)}
            draftKey={key}
            assignment={assignment}
            readOnly={phone || user.role !== 'STUDENT' || assignment.state === 'ARCHIVED'}
          />
        </section>
      </div>
    </>
  )
}
function DraftLoader({
  draftKey,
  ...props
}: {
  draftKey: DraftKey
  assignment: Schema['AssignmentView']
  readOnly: boolean
}) {
  const [loaded, setLoaded] = useState<{ draft: Draft | null; warning?: string } | null>(null)
  useEffect(() => {
    let cancelled = false
    const memory = currentDraft()
    const same =
      memory &&
      memory.userId === draftKey.userId &&
      memory.assignmentId === draftKey.assignmentId &&
      memory.problemId === draftKey.problemId &&
      memory.language === draftKey.language
    void loadDraft(draftKey)
      .then((draft) => {
        if (!cancelled) setLoaded({ draft: same ? memory : draft })
      })
      .catch(() => {
        if (!cancelled)
          setLoaded({
            draft: same ? memory : null,
            warning: '本机草稿不可用，请及时复制或导出代码。',
          })
      })
    return () => {
      cancelled = true
    }
  }, [draftKey])
  if (!loaded) return <StatePanel kind="loading" title="正在恢复本账户草稿…" />
  return (
    <DraftEditor
      key={JSON.stringify(draftKey)}
      draftKey={draftKey}
      initial={loaded.draft}
      warning={loaded.warning}
      {...props}
    />
  )
}
function DraftEditor({
  draftKey,
  initial,
  warning,
  assignment,
  readOnly,
}: {
  draftKey: DraftKey
  initial: Draft | null
  warning?: string
  assignment: Schema['AssignmentView']
  readOnly: boolean
}) {
  const [code, setCode] = useState(initial?.code || '')
  const [savedAt, setSavedAt] = useState(initial?.updatedAt || '')
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState(warning || '')
  const [intent, setIntent] = useState<'FORMAL' | 'PRACTICE'>(
    assignment.state === 'CLOSED' ? 'PRACTICE' : 'FORMAL',
  )
  const [attempt, setAttempt] = useState<SubmissionAttempt | null>(null)
  const [restoring, setRestoring] = useState(!!initial?.pending)
  const [busy, setBusy] = useState(false)
  const [receipt, setReceipt] = useState<SubmissionReceipt | null>(null)
  const [retryAt, setRetryAt] = useState(0)
  const [now, setNow] = useState(() => Date.now())
  const latest = useRef({ code, pending: initial?.pending })
  const inFlight = useRef(false)
  useEffect(() => {
    let cancelled = false
    if (initial?.pending)
      void restoreSubmissionAttempt(initial.pending)
        .then((value) => {
          if (!cancelled) {
            setAttempt(value)
            setRestoring(false)
          }
        })
        .catch((e) => {
          if (!cancelled) setError((e as Error).message)
        })
    return () => {
      cancelled = true
    }
  }, [initial])
  useEffect(() => {
    if (readOnly || restoring) return
    latest.current = { code, pending: attempt?.intent }
    rememberDraft(draftKey, code, attempt?.intent)
    let cancelled = false
    const timer = setTimeout(() => {
      void saveDraft(draftKey, code, attempt?.intent)
        .then((saved) => {
          if (!cancelled && saved) {
            setSavedAt(saved)
            setDirty(false)
          }
        })
        .catch((e) => {
          if (!cancelled) setError((e as Error).message)
        })
    }, 500)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [code, attempt, draftKey, readOnly, restoring])
  useEffect(
    () => () => {
      if (!readOnly)
        void saveDraft(draftKey, latest.current.code, latest.current.pending).catch(() => {})
    },
    [draftKey, readOnly],
  )
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  useEffect(() => {
    if (!retryAt) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [retryAt])
  function edited(value: string) {
    setCode(value)
    setDirty(true)
    latest.current.code = value
    rememberDraft(draftKey, value, latest.current.pending)
  }
  async function submit() {
    if (inFlight.current) return
    inFlight.current = true
    setBusy(true)
    setError('')
    let current = attempt
    try {
      current ??= await createSubmissionAttempt({
        assignment_id: draftKey.assignmentId,
        problem_id: draftKey.problemId,
        language_key: draftKey.language,
        code,
        intent,
      })
      setAttempt(current)
      latest.current.pending = current.intent
      rememberDraft(draftKey, latest.current.code, current.intent)
      const saved = await saveDraft(draftKey, latest.current.code, current.intent)
      if (!saved) throw new Error('会话已变更，提交已停止。')
      const accepted = await current.send(teaching.submissions.send)
      setReceipt(accepted)
      setAttempt(null)
      latest.current.pending = undefined
      rememberDraft(draftKey, latest.current.code)
      await saveDraft(draftKey, latest.current.code)
    } catch (e) {
      setError((e as Error).message)
      if (e instanceof ApiError && e.detail?.retry_after_seconds) {
        setNow(Date.now())
        setRetryAt(Date.now() + e.detail.retry_after_seconds * 1000)
      }
      if (current && !current.uncertain) {
        setAttempt(null)
        latest.current.pending = undefined
        rememberDraft(draftKey, latest.current.code)
        void saveDraft(draftKey, latest.current.code).catch(() => {})
      }
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }
  const ResultPanel = teaching.ResultPanel
  return (
    <>
      {readOnly ? (
        <TextArea label="代码草稿（只读）" value={code} readOnly rows={14} />
      ) : (
        <Suspense fallback={<StatePanel kind="loading" title="正在载入代码编辑器…" />}>
          <CodeEditor value={code} language={draftKey.language} onChange={edited} />
        </Suspense>
      )}
      <p className="field-hint">Tab 可离开编辑器。代码按账户、作业、题目和语言分别保存。</p>
      <div className="editor-actions">
        <label>
          提交意图
          <select
            aria-label="提交意图"
            value={intent}
            onChange={(e) => setIntent(e.target.value as 'FORMAL' | 'PRACTICE')}
            disabled={!!attempt || readOnly}
          >
            <option value="FORMAL">正式提交</option>
            <option value="PRACTICE">练习提交</option>
          </select>
        </label>
        <Button
          onClick={() => void submit()}
          busy={busy}
          disabled={readOnly || restoring || now < retryAt}
        >
          {attempt?.uncertain ? '核对上次提交' : '提交代码'}
        </Button>
        <Button
          variant="quiet"
          onClick={() =>
            downloadText(`astra-code.${draftKey.language === 'python3' ? 'py' : 'cpp'}`, code)
          }
        >
          导出代码
        </Button>
      </div>
      <p role="status" className="save-status">
        {dirty ? '正在保存草稿…' : savedAt ? `已保存于 ${beijingTime(savedAt)}` : '尚无本机草稿'}
      </p>
      {attempt?.uncertain && (
        <p role="status">上次受理状态尚未确认，核对将重放同一份代码快照和请求编号。</p>
      )}
      {now < retryAt && <p>请在 {Math.ceil((retryAt - now) / 1000)} 秒后手动重试。</p>}
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {receipt &&
        (ResultPanel ? (
          <ResultPanel submissionId={receipt.submission_id} onClose={() => setReceipt(null)} />
        ) : (
          <p role="status">提交已受理，编号 {receipt.submission_id}。结果组件尚未接入。</p>
        ))}
    </>
  )
}
