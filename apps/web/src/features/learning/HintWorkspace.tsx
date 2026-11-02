import { useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../app/runtime'
import { ApiError } from '../../lib/api/client'
import type { components } from '../../lib/api/schema'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'
import { TextArea } from '../../components/ui/TextArea'
import { StatePanel } from '../../components/ui/StatePanel'
import { SafeMarkdown } from '../../components/ui/SafeMarkdown'
import { beijingTime } from '../assignments/time'

type Create = components['schemas']['CreateHint']
type Rating = components['schemas']['HintRating']['rating']
type Version = components['schemas']['FeedbackVersion']
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const labels = {
  error_category: '错误类别',
  location_clues: '定位线索',
  checks: '检查方向',
  learning_advice: '学习建议',
} as const

export function HintWorkspace({
  ownerId,
  submissionId,
}: {
  ownerId: string
  submissionId?: string
}) {
  const cache = useQueryClient()
  const history = useInfiniteQuery({
    queryKey: ['hintHistory', ownerId],
    queryFn: ({ pageParam }) => api.hintHistory(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
    staleTime: 0,
    gcTime: 0,
  })

  const [lookup, setLookup] = useState('')
  const [selected, setSelected] = useState('')
  const [attempt, setAttempt] = useState(0)
  function open(id: string) {
    setLookup(id)
    setSelected(id)
    setAttempt((n) => n + 1)
  }
  function accepted(id: string) {
    void cache.invalidateQueries({ queryKey: ['hintHistory', ownerId] })
    open(id)
  }
  return (
    <section className="stack" aria-label="学习提示">
      <h2>学习提示</h2>
      <HintRequest key={submissionId || ''} submissionId={submissionId} onAccepted={accepted} />
      <section className="panel stack" aria-label="提示历史">
        <h3>提示历史</h3>
        {history.isPending ? (
          <StatePanel kind="loading" title="正在读取提示历史…" />
        ) : history.isError ? (
          <StatePanel
            kind="error"
            title="提示历史暂不可用"
            description={history.error.message}
            onRetry={() => void history.refetch()}
          />
        ) : (
          <>
            {history.data.pages[0].items.length === 0 ? (
              <p>尚无提示请求。</p>
            ) : (
              <ul className="resource-list">
                {history.data.pages
                  .flatMap((page) => page.items)
                  .map((item) => (
                    <li key={item.hint_id}>
                      <Button variant="quiet" onClick={() => open(item.hint_id)}>
                        {item.hint_id}
                      </Button>
                      <span>{beijingTime(item.created_at)}（北京时间）</span>
                    </li>
                  ))}
              </ul>
            )}
            {history.hasNextPage && (
              <Button
                variant="secondary"
                busy={history.isFetchingNextPage}
                onClick={() => void history.fetchNextPage()}
              >
                加载更多提示
              </Button>
            )}
          </>
        )}
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault()
            if (uuid.test(lookup.trim())) open(lookup.trim())
          }}
        >
          <Field
            label="提示编号"
            value={lookup}
            onChange={(e) => setLookup(e.target.value)}
            placeholder="输入提示 UUID"
          />
          <Button type="submit" disabled={!uuid.test(lookup.trim())}>
            查阅提示
          </Button>
        </form>
      </section>
      {selected && <HintDetail key={selected + ':' + attempt} id={selected} />}
    </section>
  )
}
function HintRequest({
  submissionId,
  onAccepted,
}: {
  submissionId?: string
  onAccepted: (id: string) => void
}) {
  const [source, setSource] = useState(submissionId ?? '')
  const [helpId, setHelpId] = useState('')
  const help = useQuery({
    queryKey: ['submissionFeedback', helpId],
    queryFn: () => api.submissionFeedback(helpId),
    enabled: !!helpId,
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
  })
  const [question, setQuestion] = useState('')
  const [consent, setConsent] = useState(false)
  const [pending, setPending] = useState<Create | null>(null)
  const request = useMutation({
    mutationFn: api.createHint,
    onSuccess: (value) => {
      setPending(null)
      setConsent(false)
      onAccepted(value.hint_id)
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status >= 400 && error.status < 500) setPending(null)
    },
  })
  const uncertain =
    !!pending &&
    !!request.error &&
    (!(request.error instanceof ApiError) ||
      request.error.status === 0 ||
      (request.error.status >= 500 &&
        !['MODEL_DISABLED', 'INTEGRATION_UNAVAILABLE'].includes(request.error.code)))
  const locked = uncertain || request.isPending
  return (
    <form
      className="panel stack"
      onSubmit={(e) => {
        e.preventDefault()
        if (!consent || !uuid.test(source.trim()) || request.isPending) return
        const body =
          uncertain && pending
            ? pending
            : {
                submission_id: source.trim(),
                data_sharing_consent: true as const,
                request_key: crypto.randomUUID(),
                ...(question.trim() ? { question: question.trim() } : {}),
              }
        setPending(body)
        request.mutate(body)
      }}
    >
      <h3>为已完成的提交请求提示</h3>
      <Field
        label="来源提交编号"
        value={source}
        onChange={(e) => {
          setSource(e.target.value)
          setConsent(false)
          setHelpId('')
          request.reset()
        }}
        disabled={locked}
        hint="可从错题记录选择，或输入本人的提交编号。"
      />
      <Button
        variant="secondary"
        disabled={!uuid.test(source.trim()) || help.isFetching}
        onClick={() => {
          if (helpId === source.trim()) void help.refetch()
          else setHelpId(source.trim())
        }}
      >
        查看本轮固定帮助
      </Button>
      {helpId &&
        (help.isFetching || help.isPending ? (
          <p role="status">正在读取固定帮助…</p>
        ) : help.isError ? (
          <p role="alert">{help.error.message}</p>
        ) : (
          <FrozenHelp value={help.data} />
        ))}
      <TextArea
        label="想问的问题（可选）"
        maxLength={500}
        value={question}
        disabled={locked}
        onChange={(e) => setQuestion(e.target.value)}
      />
      <label className="button-row">
        <input
          type="checkbox"
          checked={consent}
          disabled={locked}
          onChange={(e) => setConsent(e.target.checked)}
        />
        我同意本次将本人代码、问题、公开题面和样例、脱敏诊断与判定发送给模型。
      </label>
      <Button
        type="submit"
        busy={request.isPending}
        disabled={!consent || !uuid.test(source.trim())}
      >
        {uncertain ? '核对上次请求' : '请求提示'}
      </Button>
      {request.error && (
        <p role="alert" className="form-error">
          {request.error.message} {uncertain ? '受理结果尚未确认，可使用同一请求编号核对。' : ''}
          {request.error instanceof ApiError && request.error.detail?.retry_after_seconds
            ? `可在 ${request.error.detail.retry_after_seconds} 秒后重试。`
            : ''}
        </p>
      )}
    </form>
  )
}
function FrozenHelp({ value }: { value: Version }) {
  return (
    <section className="stack" aria-label="固定帮助">
      <h4>{value.title}</h4>
      <SafeMarkdown>{value.explanation}</SafeMarkdown>
      <ul>
        {value.checklist.map((line, n) => (
          <li key={n}>
            <SafeMarkdown>{line}</SafeMarkdown>
          </li>
        ))}
      </ul>
      <p>固定帮助版本 {value.feedback_version_id}</p>
    </section>
  )
}
function HintDetail({ id }: { id: string }) {
  const [rating, setRating] = useState<Rating>('USEFUL')
  const [comment, setComment] = useState('')

  const hint = useQuery({
    queryKey: ['studentHint', id],
    queryFn: () => api.hint(id),
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
    refetchInterval: (q) => (!q.state.error && q.state.data?.status === 'PENDING' ? 5000 : false),
  })
  if (hint.isError)
    return (
      <StatePanel
        kind="error"
        title="提示暂不可用"
        description={hint.error.message}
        onRetry={() => void hint.refetch()}
      />
    )
  if (hint.isPending || (hint.isFetching && hint.data.status !== 'PENDING'))
    return <StatePanel kind="loading" title="正在核对提示访问权限…" />
  const value = hint.data
  return (
    <section className="panel stack" aria-label="提示详情">
      <h3>提示详情</h3>
      <p className="template-text">
        来源提交 {value.submission_id} · {beijingTime(value.created_at)}（北京时间）
      </p>
      {value.status === 'READY' && value.sections ? (
        <>
          <p className="notice">建议需自行验证。</p>
          {Object.entries(labels).map(([name, title]) => (
            <section key={name}>
              <h4>{title}</h4>
              <SafeMarkdown>{value.sections![name as keyof typeof labels]}</SafeMarkdown>
            </section>
          ))}
          <p className="template-text">
            模型版本 {value.model_version} · 模板版本 {value.template_version_id}
          </p>
          <HintRating
            id={id}
            rating={rating}
            setRating={setRating}
            comment={comment}
            setComment={setComment}
          />
        </>
      ) : (
        <p role="status">
          {value.status === 'PENDING'
            ? '请求已受理，正在等待提示。'
            : value.status === 'BLOCKED'
              ? '当前策略限制了此提示。'
              : '提示暂不可用。'}{' '}
          {value.reason_code}
        </p>
      )}
      {value.fallback_feedback && <FrozenHelp value={value.fallback_feedback} />}
    </section>
  )
}
function HintRating({
  id,
  rating,
  setRating,
  comment,
  setComment,
}: {
  id: string
  rating: Rating
  setRating: (rating: Rating) => void
  comment: string
  setComment: (comment: string) => void
}) {
  const save = useMutation({
    mutationFn: () =>
      api.rateHint(id, { rating, ...(comment.trim() ? { comment: comment.trim() } : {}) }),
  })
  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault()
        if (!save.isPending) save.mutate()
      }}
    >
      <label className="field">
        评价此提示
        <select
          value={rating}
          disabled={save.isPending}
          onChange={(e) => {
            setRating(e.target.value as Rating)
            save.reset()
          }}
        >
          <option value="USEFUL">有帮助</option>
          <option value="NOT_USEFUL">没有帮助</option>
          <option value="ERROR">内容有误</option>
        </select>
      </label>
      <TextArea
        label="评价说明（可选）"
        value={comment}
        maxLength={500}
        disabled={save.isPending}
        onChange={(e) => {
          setComment(e.target.value)
          save.reset()
        }}
      />
      <Button type="submit" busy={save.isPending}>
        保存评价
      </Button>
      {save.isSuccess && <p role="status">评价已保存，可重新修改。</p>}
      {save.error && <p role="alert">{save.error.message}</p>}
    </form>
  )
}
