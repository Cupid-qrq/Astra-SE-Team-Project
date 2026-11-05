import { useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'
import { TextArea } from '../../components/ui/TextArea'
import { SafeMarkdown } from '../../components/ui/SafeMarkdown'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { StatePanel } from '../../components/ui/StatePanel'
import { readHelpDraft, writeHelpDraft, type HelpFields } from './feedbackDrafts'
import type { components } from '../../lib/api/schema'

type Body = components['schemas']['FeedbackDraft']
export function FeedbackFields({
  value,
  onChange,
  disabled = false,
}: {
  value: HelpFields
  onChange: (value: HelpFields) => void
  disabled?: boolean
}) {
  return (
    <fieldset className="material-fields stack" disabled={disabled}>
      <Field
        label="帮助标题"
        value={value.title}
        required
        maxLength={100}
        onChange={(e) => onChange({ ...value, title: e.target.value })}
      />
      <TextArea
        label="帮助说明"
        value={value.explanation}
        required
        maxLength={2000}
        rows={6}
        onChange={(e) => onChange({ ...value, explanation: e.target.value })}
      />
      <TextArea
        label="检查清单（每行一项）"
        value={value.checklistText}
        rows={5}
        hint="最多10项，每项最多500字。说明、标题与清单合计最多2000字。"
        onChange={(e) => onChange({ ...value, checklistText: e.target.value })}
      />
    </fieldset>
  )
}

export function FeedbackEditor({
  initial,
  ownerId,
  onReload,
}: {
  initial: components['schemas']['FeedbackDraftView']
  ownerId: string
  onReload: () => Promise<unknown>
}) {
  const cid = initial.catalog_id
  const [fields, setFields] = useState<HelpFields>(() => ({
    title: initial.title,
    explanation: initial.explanation,
    checklistText: initial.checklist.join('\n'),
  }))
  const [saved, setSaved] = useState(fields)
  const [revision, setRevision] = useState(initial.revision)
  const [active, setActive] = useState(initial.active_version_no ?? null)
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState<components['schemas']['PublishCommand'] | null>(null)
  const [recovery, setRecovery] = useState(() => readHelpDraft(ownerId, cid))
  const [storageFailed, setStorageFailed] = useState(false)
  const [notice, setNotice] = useState('')
  const cache = useQueryClient()
  const dirty = JSON.stringify(fields) !== JSON.stringify(saved)
  const archived = initial.course_status === 'ARCHIVED'
  const save = useMutation({
    mutationFn: (body: components['schemas']['UpdateFeedback']) => api.saveFeedbackDraft(cid, body),
    onSuccess: (result, body) => {
      setRevision(result.revision)
      setSaved({
        title: body.title,
        explanation: body.explanation,
        checklistText: body.checklist.join('\n'),
      })
      setFields({
        title: body.title,
        explanation: body.explanation,
        checklistText: body.checklist.join('\n'),
      })
      setNotice('草稿已保存，尚未发布。')
      writeHelpDraft(ownerId, cid, null)
      setRecovery(null)
      cache.setQueryData<components['schemas']['FeedbackDraftView']>(
        ['feedbackDraft', cid],
        (current) => ({
          ...(current ?? initial),
          title: body.title,
          explanation: body.explanation,
          checklist: body.checklist,
          revision: result.revision,
        }),
      )
      void cache.invalidateQueries({ queryKey: ['feedbackCatalogs'] })
    },
  })
  const publish = useMutation({
    mutationFn: (body: components['schemas']['PublishCommand']) => api.publishFeedback(cid, body),
    onSuccess: (result, body) => {
      setRevision(body.expected_revision + 1)
      setActive((number) => (number ?? 0) + 1)
      setReason('')
      setPending(null)
      setNotice('新版本已生效，历史版本保持不变。')
      cache.setQueryData<components['schemas']['FeedbackDraftView']>(
        ['feedbackDraft', cid],
        (current) => ({
          ...(current ?? initial),
          revision: body.expected_revision + 1,
          active_version_id: result.version_id,
          active_version_no: (active ?? 0) + 1,
        }),
      )
      void cache.invalidateQueries({ queryKey: ['feedbackHistory', cid] })
      void cache.invalidateQueries({ queryKey: ['feedbackCatalogs'] })
    },
    onError: () => setPending(null),
  })
  function edit(next: HelpFields) {
    setFields(next)
    setRecovery(null)
    const changed = JSON.stringify(next) !== JSON.stringify(saved)
    setStorageFailed(!writeHelpDraft(ownerId, cid, changed ? { revision, fields: next } : null))
  }
  const body: Body = {
    title: fields.title,
    explanation: fields.explanation,
    checklist: fields.checklistText.split('\n').filter((line) => line.length > 0),
  }
  const count = [...(body.title + body.explanation + body.checklist.join(''))].length
  const invalid =
    !body.title.trim() ||
    !body.explanation.trim() ||
    body.checklist.length > 10 ||
    body.checklist.some((line) => !line.trim() || [...line].length > 500) ||
    count > 2000 ||
    new TextEncoder().encode(body.title + body.explanation + body.checklist.join('')).length > 8192
  const busy = save.isPending || publish.isPending || pending !== null
  return (
    <>
      <p className="notice">
        <strong>{active === null ? '尚未发布' : `生效版本：${active}`}</strong> · 草稿版本{' '}
        {revision}
        。发布后仅新的评测使用新版本，历史引用不变。
      </p>
      {archived && <p className="notice">课程已归档，判题帮助只读。</p>}
      {recovery && (
        <div className="notice stack">
          <p>
            本账号有未保存的编辑，可恢复后核对。恢复后若发现他人已修改同一内容，会提示你重新核对。
          </p>
          <div className="button-row">
            <Button
              variant="secondary"
              disabled={archived || busy}
              onClick={() => {
                setFields(recovery.fields)
                setRevision(recovery.revision)
                setRecovery(null)
                setNotice('已恢复本地编辑，请核对后保存。')
              }}
            >
              恢复本地编辑
            </Button>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => {
                writeHelpDraft(ownerId, cid, null)
                setRecovery(null)
              }}
            >
              放弃本地恢复
            </Button>
          </div>
        </div>
      )}
      <div className="feedback-layout">
        <form
          className="panel stack"
          onSubmit={(e) => {
            e.preventDefault()
            if (!invalid && !busy && !archived)
              save.mutate({ ...body, expected_revision: revision })
          }}
        >
          <h2>编辑草稿</h2>
          <FeedbackFields value={fields} onChange={edit} disabled={busy || archived} />
          <p className={invalid ? 'form-error' : 'muted'}>
            {count}/2000字{invalid ? '，请检查必填内容与清单上限。' : ''}
          </p>
          {storageFailed && (
            <p role="alert">浏览器无法保留本地恢复副本，请在离开前复制未保存内容。</p>
          )}
          <div className="button-row">
            <Button
              type="submit"
              busy={save.isPending}
              disabled={invalid || busy || archived || !dirty}
            >
              保存草稿
            </Button>
          </div>
          <TextArea
            label="发布理由"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={500}
            rows={3}
            disabled={busy || archived}
            hint="10—500字，仅发布已保存的草稿。"
          />
          <Button
            type="button"
            disabled={dirty || invalid || busy || archived || [...reason.trim()].length < 10}
            onClick={() => setPending({ expected_revision: revision, reason: reason.trim() })}
          >
            发布新版本
          </Button>
          {dirty && <p className="muted">存在未保存的修改，请先保存草稿再发布。</p>}
          {(save.error || publish.error) && (
            <div role="alert" className="form-error stack">
              <p>{(save.error || publish.error)?.message} 当前编辑内容已保留。</p>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={async () => {
                  await onReload()
                  save.reset()
                  publish.reset()
                }}
              >
                重新载入服务器草稿（保留本地恢复）
              </Button>
            </div>
          )}
          {notice && <p role="status">{notice}</p>}
        </form>
        <section className="panel stack" aria-label="草稿预览">
          <h2>草稿预览</h2>
          <h3>{body.title || '帮助标题'}</h3>
          <SafeMarkdown>{body.explanation}</SafeMarkdown>
          <ul>
            {body.checklist.map((line, i) => (
              <li key={i}>
                <SafeMarkdown>{line}</SafeMarkdown>
              </li>
            ))}
          </ul>
          <p className="muted">此处为尚未发布的内容。</p>
        </section>
      </div>
      <FeedbackHistory catalogId={cid} />
      <ConfirmDialog
        open={pending !== null}
        title="发布判题帮助新版本"
        description={`将发布已保存的草稿版本 ${pending?.expected_revision ?? ''}；之前的版本和历史评测继续使用原内容。`}
        confirmLabel="确认发布"
        busy={publish.isPending}
        onCancel={() => setPending(null)}
        onConfirm={() => {
          if (pending) publish.mutate(pending)
        }}
      >
        <p>{pending?.reason}</p>
      </ConfirmDialog>
    </>
  )
}

function FeedbackHistory({ catalogId }: { catalogId: string }) {
  const [selected, setSelected] = useState<number | null>(null)
  const history = useInfiniteQuery({
    queryKey: ['feedbackHistory', catalogId],
    queryFn: ({ pageParam }) => api.feedbackHistory(catalogId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
  })
  const version = useQuery({
    queryKey: ['feedbackVersion', catalogId, selected],
    queryFn: () => api.feedbackVersion(catalogId, selected!),
    enabled: selected !== null,
  })
  return (
    <section className="stack" aria-label="已发布版本">
      <h2>已发布版本</h2>
      {history.isPending ? (
        <StatePanel kind="loading" title="正在读取版本…" />
      ) : history.isError ? (
        <StatePanel
          kind="error"
          title="版本历史暂不可用"
          description={history.error.message}
          onRetry={() => void history.refetch()}
        />
      ) : (
        <>
          <ul className="resource-list">
            {history.data.pages
              .flatMap((p) => p.items)
              .sort((a, b) => b.version_no - a.version_no)
              .map((item) => (
                <li key={item.version_id}>
                  <strong>
                    版本 {item.version_no} · {item.title}
                  </strong>
                  <span>
                    {new Intl.DateTimeFormat('zh-CN', {
                      timeZone: 'Asia/Shanghai',
                      dateStyle: 'short',
                      timeStyle: 'short',
                    }).format(new Date(item.published_at))}
                    （北京时间）
                  </span>
                  <Button variant="secondary" onClick={() => setSelected(item.version_no)}>
                    查看版本 {item.version_no}
                  </Button>
                </li>
              ))}
          </ul>
          {history.data.pages[0].items.length === 0 && <p>尚无已发布版本。</p>}
          {history.hasNextPage && (
            <Button
              variant="secondary"
              busy={history.isFetchingNextPage}
              onClick={() => void history.fetchNextPage()}
            >
              加载更多版本
            </Button>
          )}
        </>
      )}
      {selected !== null && (
        <section className="panel stack" aria-label="历史版本预览">
          <h3>已发布版本 {selected}</h3>
          {version.isPending ? (
            <p role="status">正在读取版本…</p>
          ) : version.isError ? (
            <StatePanel
              kind="error"
              title="版本暂不可用"
              description={version.error.message}
              onRetry={() => void version.refetch()}
            />
          ) : (
            <>
              <h4>{version.data.title}</h4>
              <SafeMarkdown>{version.data.explanation}</SafeMarkdown>
              <ul>
                {version.data.checklist.map((line, i) => (
                  <li key={i}>
                    <SafeMarkdown>{line}</SafeMarkdown>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </section>
  )
}
