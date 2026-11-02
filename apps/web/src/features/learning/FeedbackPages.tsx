import { useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, sessionKey } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { DataTable } from '../../components/ui/DataTable'
import { StatePanel } from '../../components/ui/StatePanel'
import { FeedbackEditor, FeedbackFields } from './FeedbackEditor'
import { readHelpDraft, writeHelpDraft, type HelpFields } from './feedbackDrafts'
import type { components } from '../../lib/api/schema'

export function FeedbackCatalogsPage() {
  const session = useQuery({ queryKey: sessionKey, queryFn: api.session })
  const [search] = useSearchParams()
  const courseId = search.get('course_id') || undefined
  const role = session.data?.user?.role
  const allowed = role === 'TEACHER' || role === 'ADMIN'
  const course = useQuery({
    queryKey: ['course', courseId],
    queryFn: () => api.course(courseId!),
    enabled: allowed && role === 'TEACHER' && !!courseId,
  })
  const catalogs = useInfiniteQuery({
    queryKey: ['feedbackCatalogs', courseId, role],
    queryFn: ({ pageParam }) => api.feedbackCatalogs(courseId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
    enabled: allowed,
  })
  const [creating, setCreating] = useState(false)
  if (!allowed)
    return (
      <StatePanel
        kind="forbidden"
        title="无权维护固定帮助"
        description="请使用任课教师或全局管理员账号。"
      />
    )
  const global = role === 'ADMIN'
  const root = global ? '/admin/feedback' : '/teacher/feedback'
  return (
    <>
      {!global && (
        <Link className="back-link" to={courseId ? `/courses/${courseId}` : '/courses'}>
          ← 返回课程
        </Link>
      )}
      <header className="page-heading">
        <div>
          <h1>{global ? '全局固定帮助' : '课程固定帮助'}</h1>
          <p>{course.data?.title || '维护错误说明与检查清单；已发布版本永久保留。'}</p>
        </div>
        {(global || course.data?.status === 'ACTIVE') && (
          <Button onClick={() => setCreating((v) => !v)}>
            {creating ? '收起新建表单' : '新建固定帮助'}
          </Button>
        )}
      </header>
      {course.isError && (
        <StatePanel
          kind="error"
          title="课程不可用"
          description={course.error.message}
          onRetry={() => void course.refetch()}
        />
      )}
      {!global && !courseId && (
        <p className="notice">此处列出本人课程的帮助。从课程中的“管理固定帮助”进入可新建草稿。</p>
      )}
      {course.data?.status === 'ARCHIVED' && <p className="notice">课程已归档，固定帮助只读。</p>}
      {creating && (global || course.data?.status === 'ACTIVE') && (
        <CreateFeedbackForm
          key={`${global}:${courseId ?? ''}`}
          courseId={courseId}
          global={global}
          ownerId={session.data!.user!.user_id}
        />
      )}
      {catalogs.isPending ? (
        <StatePanel kind="loading" title="正在读取帮助目录…" />
      ) : catalogs.isError ? (
        <StatePanel
          kind="error"
          title="帮助目录暂不可用"
          description={catalogs.error.message}
          onRetry={() => void catalogs.refetch()}
        />
      ) : (
        <DataTable
          caption="固定帮助目录"
          rows={catalogs.data.pages.flatMap((p) => p.items)}
          rowKey={(row) => row.catalog_id}
          empty="尚无固定帮助，可按判定和语言新建。"
          columns={[
            {
              key: 'title',
              heading: '草稿标题',
              render: (row) => <Link to={`${root}/${row.catalog_id}`}>{row.title}</Link>,
            },
            {
              key: 'scope',
              heading: '范围',
              render: (row) => (row.scope === 'GLOBAL' ? '全局' : '课程'),
            },
            { key: 'revision', heading: '草稿修订', render: (row) => row.revision },
          ]}
        />
      )}
      {catalogs.hasNextPage && (
        <Button
          variant="secondary"
          busy={catalogs.isFetchingNextPage}
          onClick={() => void catalogs.fetchNextPage()}
        >
          加载更多帮助
        </Button>
      )}
    </>
  )
}

function CreateFeedbackForm({
  courseId,
  global,
  ownerId,
}: {
  courseId?: string
  global: boolean
  ownerId: string
}) {
  const recoveryId = global ? 'new:GLOBAL' : `new:COURSE:${courseId}`
  const [recovery, setRecovery] = useState(() => readHelpDraft(ownerId, recoveryId))
  const [storageFailed, setStorageFailed] = useState(false)
  const [fields, setFields] = useState<HelpFields>({
    title: '',
    explanation: '',
    checklistText: '',
  })
  const [verdict, setVerdict] = useState<components['schemas']['CreateFeedback']['verdict']>('WA')
  const [language, setLanguage] =
    useState<components['schemas']['CreateFeedback']['language_key']>('ALL')
  const navigate = useNavigate()
  const create = useMutation({
    mutationFn: api.createFeedback,
    onSuccess: (value) => {
      writeHelpDraft(ownerId, recoveryId, null)
      navigate(`${global ? '/admin/feedback' : '/teacher/feedback'}/${value.catalog_id}`)
    },
  })
  function preserve(nextFields = fields, nextVerdict = verdict, nextLanguage = language) {
    setRecovery(null)
    setStorageFailed(
      !writeHelpDraft(ownerId, recoveryId, {
        revision: 1,
        fields: nextFields,
        creation: { verdict: nextVerdict, language: nextLanguage },
      }),
    )
  }
  return (
    <form
      className="panel stack"
      onSubmit={(e) => {
        e.preventDefault()
        create.mutate({
          scope: global ? 'GLOBAL' : 'COURSE',
          ...(global ? {} : { course_id: courseId }),
          language_key: language,
          verdict,
          draft: {
            title: fields.title,
            explanation: fields.explanation,
            checklist: fields.checklistText.split('\n').filter((line) => line.length > 0),
          },
        })
      }}
    >
      <h2>新建固定帮助</h2>
      {recovery && (
        <div className="notice">
          <p>本账号在此范围有未完成的新建草稿，可恢复后核对。</p>
          <Button
            variant="secondary"
            onClick={() => {
              setFields(recovery.fields)
              setVerdict(recovery.creation?.verdict ?? 'WA')
              setLanguage(global ? 'ALL' : (recovery.creation?.language ?? 'ALL'))
              setRecovery(null)
            }}
          >
            恢复新建草稿
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              writeHelpDraft(ownerId, recoveryId, null)
              setRecovery(null)
            }}
          >
            放弃新建恢复
          </Button>
        </div>
      )}
      <div className="button-row">
        <label className="field">
          判定类别
          <select
            aria-label="判定类别"
            value={verdict}
            disabled={create.isPending}
            onChange={(e) => {
              const next = e.target.value as typeof verdict
              setVerdict(next)
              preserve(fields, next)
            }}
          >
            {['CE', 'WA', 'TLE', 'RE', 'SE'].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label className="field">
          适用语言
          <select
            aria-label="适用语言"
            value={language}
            disabled={global || create.isPending}
            onChange={(e) => {
              const next = e.target.value as typeof language
              setLanguage(next)
              preserve(fields, verdict, next)
            }}
          >
            <option value="ALL">全部语言</option>
            <option value="cpp17">C++17</option>
            <option value="python3">Python 3</option>
          </select>
        </label>
      </div>
      <FeedbackFields
        value={fields}
        onChange={(next) => {
          setFields(next)
          preserve(next)
        }}
        disabled={create.isPending}
      />
      {storageFailed && <p role="alert">浏览器无法保留新建草稿，请在离开前复制内容。</p>}
      <Button type="submit" busy={create.isPending}>
        创建草稿
      </Button>
      {create.error && (
        <p className="form-error" role="alert">
          {create.error.message} 填写内容已保留。
        </p>
      )}
    </form>
  )
}

export function FeedbackDetailPage() {
  const { id = '' } = useParams()
  const session = useQuery({ queryKey: sessionKey, queryFn: api.session })
  const role = session.data?.user?.role
  const allowed = role === 'TEACHER' || role === 'ADMIN'
  const draft = useQuery({
    queryKey: ['feedbackDraft', id],
    queryFn: () => api.feedbackDraft(id),
    enabled: allowed,
    refetchOnWindowFocus: false,
  })
  const [epoch, setEpoch] = useState(0)
  if (!allowed)
    return (
      <StatePanel
        kind="forbidden"
        title="无权维护固定帮助"
        description="请使用任课教师或全局管理员账号。"
      />
    )
  if (draft.isPending) return <StatePanel kind="loading" title="正在读取帮助草稿…" />
  if (draft.isError)
    return (
      <StatePanel
        kind="error"
        title="草稿暂不可用"
        description={draft.error.message}
        onRetry={() => void draft.refetch()}
      />
    )
  const root = role === 'ADMIN' ? '/admin/feedback' : '/teacher/feedback'
  return (
    <>
      <Link
        className="back-link"
        to={root + (draft.data.course_id ? `?course_id=${draft.data.course_id}` : '')}
      >
        ← 返回帮助目录
      </Link>
      <header className="page-heading">
        <div>
          <h1>编辑固定帮助</h1>
          <p>
            {draft.data.verdict} ·{' '}
            {draft.data.language_key === 'ALL' ? '全部语言' : draft.data.language_key}
          </p>
        </div>
      </header>
      <FeedbackEditor
        key={`${id}:${epoch}`}
        initial={draft.data}
        ownerId={session.data!.user!.user_id}
        onReload={async () => {
          const result = await draft.refetch()
          if (result.isSuccess) setEpoch((n) => n + 1)
        }}
      />
    </>
  )
}
