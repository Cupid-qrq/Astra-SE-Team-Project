import { useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, sessionKey } from '../../app/runtime'
import { StatePanel } from '../../components/ui/StatePanel'
import { Button } from '../../components/ui/Button'
import { DataTable } from '../../components/ui/DataTable'
import { TemplateEditor } from './TemplateEditor'

function useTemplateAccess() {
  const session = useQuery({ queryKey: sessionKey, queryFn: api.session })
  const global = useLocation().pathname.startsWith('/admin/')
  const user = session.data?.user
  return {
    global,
    ownerId: user?.user_id,
    allowed: user?.role === (global ? 'ADMIN' : 'TEACHER'),
    root: global ? '/admin/hint-templates' : '/teacher/hint-templates',
  }
}
const forbidden = (
  <StatePanel kind="forbidden" title="无权维护提示模板" description="请从本账号的工作区进入。" />
)
export function TemplatesPage() {
  const { allowed, global, root, ownerId } = useTemplateAccess()
  const [params] = useSearchParams()
  const courseId = global ? undefined : params.get('course_id') || undefined
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const course = useQuery({
    queryKey: ['course', courseId],
    queryFn: () => api.course(courseId!),
    enabled: allowed && !!courseId,
  })
  const list = useInfiniteQuery({
    queryKey: ['templates', global, courseId],
    queryFn: ({ pageParam }) => api.templates(courseId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
    enabled: allowed,
  })
  if (!allowed) return forbidden
  const canCreate =
    (global || course.data?.status === 'ACTIVE') &&
    list.isSuccess &&
    !list.data.pages.some((page) => page.items.length)
  return (
    <>
      {!global && (
        <Link className="back-link" to={courseId ? `/courses/${courseId}` : '/courses'}>
          ← 返回课程
        </Link>
      )}
      <header className="page-heading">
        <div>
          <h1>{global ? '全局提示模板' : '课程提示模板'}</h1>
          <p>{course.data?.title || '查阅草稿，维护提示正文与允许的占位符。'}</p>
        </div>
        {canCreate && (
          <Button onClick={() => setCreating(!creating)}>
            {creating ? '收起新建表单' : '新建提示模板'}
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
      {!courseId && !global && <p className="notice">从课程中的“管理提示模板”进入可新建草稿。</p>}
      {course.data?.status === 'ARCHIVED' && <p className="notice">课程已归档，模板只读。</p>}
      {creating && canCreate && (
        <TemplateEditor
          key={courseId ?? 'global'}
          ownerId={ownerId!}
          courseId={courseId}
          onCreated={(id) => navigate(`${root}/${id}`)}
        />
      )}
      {list.isPending ? (
        <StatePanel kind="loading" title="正在读取模板目录…" />
      ) : list.isError ? (
        <StatePanel
          kind="error"
          title="模板目录暂不可用"
          description={list.error.message}
          onRetry={() => void list.refetch()}
        />
      ) : (
        <DataTable
          caption="提示模板目录"
          rows={list.data.pages.flatMap((p) => p.items)}
          rowKey={(row) => row.template_id}
          empty="尚无提示模板。"
          columns={[
            {
              key: 'id',
              heading: '模板编号',
              render: (row) => <Link to={`${root}/${row.template_id}`}>{row.template_id}</Link>,
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
      {list.hasNextPage && (
        <Button
          variant="secondary"
          busy={list.isFetchingNextPage}
          onClick={() => void list.fetchNextPage()}
        >
          加载更多模板
        </Button>
      )}
    </>
  )
}
export function TemplatePage() {
  const { id = '' } = useParams()
  const { allowed, root, ownerId } = useTemplateAccess()
  const [epoch, setEpoch] = useState(0)
  const draft = useQuery({
    queryKey: ['templateDraft', id],
    queryFn: () => api.templateDraft(id),
    enabled: allowed,
    refetchOnWindowFocus: false,
  })
  if (!allowed) return forbidden
  if (draft.isPending) return <StatePanel kind="loading" title="正在读取模板草稿…" />
  if (draft.isError)
    return (
      <StatePanel
        kind="error"
        title="模板草稿暂不可用"
        description={draft.error.message}
        onRetry={() => void draft.refetch()}
      />
    )
  return (
    <>
      <Link
        className="back-link"
        to={root + (draft.data.course_id ? `?course_id=${draft.data.course_id}` : '')}
      >
        ← 返回模板目录
      </Link>
      <header className="page-heading">
        <div>
          <h1>编辑提示模板</h1>
          <p>{draft.data.scope === 'GLOBAL' ? '全局模板' : '课程模板'}</p>
        </div>
      </header>
      <TemplateEditor
        key={`${id}:${epoch}`}
        ownerId={ownerId!}
        initial={draft.data}
        courseId={draft.data.course_id ?? undefined}
        onReload={async () => {
          if ((await draft.refetch()).isSuccess) setEpoch((n) => n + 1)
        }}
      />
      <TemplateHistory key={id} id={id} />
    </>
  )
}
function TemplateHistory({ id }: { id: string }) {
  const [selected, setSelected] = useState<number | null>(null)
  const history = useInfiniteQuery({
    queryKey: ['templateHistory', id],
    queryFn: ({ pageParam }) => api.templateHistory(id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
  })
  const version = useQuery({
    queryKey: ['templateVersion', id, selected],
    queryFn: () => api.templateVersion(id, selected!),
    enabled: selected !== null,
  })
  return (
    <section className="stack" aria-label="冻结版本历史">
      <h2>冻结版本历史</h2>
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
              .map((item) => (
                <li key={item.version_id}>
                  <strong>版本 {item.version_no}</strong>
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
          {!history.data.pages[0].items.length && <p>尚无已发布版本。</p>}
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
        <section className="panel stack" aria-label="冻结版本详情">
          <h3>冻结版本 {selected}</h3>
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
              <pre className="template-text">{version.data.body}</pre>
              <p>结构版本 {version.data.schema_version}</p>
              <p>允许的占位符：{version.data.allowed_placeholders.join('、') || '无'}</p>
              <p className="template-text">校验值：{version.data.checksum}</p>
            </>
          )}
        </section>
      )}
    </section>
  )
}
