import { useEffect, useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'
import { TextArea } from '../../components/ui/TextArea'
import { StatePanel } from '../../components/ui/StatePanel'
import { beijingTime } from '../assignments/time'
import { communityApi } from './communityApi'
export function DiscussionsPage() {
  const { id = '', problemId = '' } = useParams()
  const [params] = useSearchParams()
  const version = params.get('version_id') || ''
  return (
    <DiscussionsContent
      key={`${id}:${problemId}:${version}`}
      id={id}
      problemId={problemId}
      version={version}
    />
  )
}
function DiscussionsContent({
  id,
  problemId,
  version,
}: {
  id: string
  problemId: string
  version: string
}) {
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])
  const client = useQueryClient()
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const course = useQuery({ queryKey: ['course', id], queryFn: () => api.course(id) })
  const q = useInfiniteQuery({
    queryKey: ['discussions', id, problemId, version],
    queryFn: ({ pageParam }) => communityApi.discussions(id, problemId, version, pageParam),
    enabled: !!version,
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
  })
  const create = useMutation({
    mutationFn: () =>
      communityApi.create(id, problemId, {
        version_id: version,
        title: title.trim(),
        body: body.trim(),
      }),
    onSuccess: (t) => {
      void client.invalidateQueries({ queryKey: ['discussions', id, problemId, version] })
      if (mounted.current) navigate(`/discussions/${t.thread_id}`)
    },
  })
  return (
    <div className="community-page stack">
      <Link className="back-link" to={`/courses/${id}`}>
        ← 返回课程
      </Link>
      <header className="page-heading">
        <div>
          <h1>题目讨论</h1>
          <p>讨论仅限本课程的当前题目版本</p>
        </div>
      </header>
      <p className="community-notice">
        分享思路、边界与调试方法，请勿直接发布完整答案、个人信息或隐藏测试。每次发言至少间隔 10
        秒，每小时最多 30 条。
      </p>
      {!version ? (
        <StatePanel
          kind="error"
          title="缺少题目版本"
          description="请从题目或作业页面重新进入讨论。"
        />
      ) : q.isPending ? (
        <StatePanel kind="loading" title="正在核对访问权限并加载讨论…" />
      ) : q.isError ? (
        <StatePanel
          kind="error"
          title="讨论暂不可用"
          description={q.error.message}
          onRetry={() => void q.refetch()}
        />
      ) : (
        <>
          <ul className="community-threads">
            {q.data.pages
              .flatMap((p) => p.items)
              .map((t) => (
                <li key={t.thread_id}>
                  <div className="button-row">
                    {t.pinned && <span className="status-label">置顶</span>}
                    {t.resolved && <span className="status-label">已解决</span>}
                    {t.locked && <span className="status-label">已锁定</span>}
                    <Link to={`/discussions/${t.thread_id}`}>{t.title}</Link>
                  </div>
                  <p className="muted">
                    {t.author_name} · {beijingTime(t.created_at)} · {t.reply_count} 条回复
                  </p>
                </li>
              ))}
          </ul>
          {!q.data.pages.some((p) => p.items.length) && (
            <StatePanel
              kind="empty"
              title="还没有讨论"
              description="可以从遇到的问题或已经尝试的方法开始。"
            />
          )}
          {q.hasNextPage && (
            <Button
              busy={q.isFetchingNextPage}
              variant="secondary"
              onClick={() => void q.fetchNextPage()}
            >
              加载更多讨论
            </Button>
          )}
          {course.data?.status === 'ACTIVE' && (
            <form
              className="panel stack"
              onSubmit={(e) => {
                e.preventDefault()
                create.mutate()
              }}
            >
              <h2>发起讨论</h2>
              <Field
                label="讨论标题"
                disabled={create.isPending}
                required
                maxLength={120}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
              <TextArea
                label="讨论正文"
                disabled={create.isPending}
                required
                maxLength={4000}
                rows={6}
                value={body}
                onChange={(e) => setBody(e.target.value)}
              />
              {create.error && <p role="alert">{create.error.message}</p>}
              <Button
                type="submit"
                busy={create.isPending}
                disabled={!title.trim() || !body.trim()}
              >
                发布讨论
              </Button>
            </form>
          )}
        </>
      )}
      {course.data?.status === 'ARCHIVED' && <p>课程已归档，讨论只读。</p>}
    </div>
  )
}
