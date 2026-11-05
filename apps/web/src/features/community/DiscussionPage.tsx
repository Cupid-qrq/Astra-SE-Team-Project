import { useEffect, useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { TextArea } from '../../components/ui/TextArea'
import { SafeMarkdown } from '../../components/ui/SafeMarkdown'
import { StatePanel } from '../../components/ui/StatePanel'
import { beijingTime } from '../assignments/time'
import {
  communityApi,
  discussionPath,
  type Reply,
  type Thread,
  type ThreadChange,
} from './communityApi'
export function DiscussionPage() {
  const { id = '' } = useParams()
  return <DiscussionContent key={id} id={id} />
}
function DiscussionContent({ id }: { id: string }) {
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])
  const [body, setBody] = useState('')
  const q = useInfiniteQuery({
    queryKey: ['discussion', id],
    queryFn: ({ pageParam }) => communityApi.discussion(id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
  })
  const thread = q.data?.pages[0].thread
  const course = useQuery({
    queryKey: ['course', thread?.course_id],
    queryFn: () => api.course(thread!.course_id),
    enabled: !!thread,
  })
  const reply = useMutation({
    mutationFn: () => communityApi.reply(id, body.trim()),
    onSuccess: async () => {
      if (!mounted.current) return
      setBody('')
      await q.refetch()
    },
  })
  if (q.isPending) return <StatePanel kind="loading" title="正在读取讨论…" />
  if (q.isError || !thread)
    return (
      <StatePanel
        kind="error"
        title="讨论暂不可用"
        description={q.error?.message}
        onRetry={() => void q.refetch()}
      />
    )
  const writable = course.data?.status === 'ACTIVE'
  return (
    <div className="community-page stack">
      <Link
        className="back-link"
        to={discussionPath(thread.course_id, thread.problem_id, thread.version_id)}
      >
        ← 返回题目讨论
      </Link>
      <article className="panel stack">
        <header>
          <div className="button-row">
            {thread.pinned && <span className="status-label">置顶</span>}
            {thread.resolved && <span className="status-label">已解决</span>}
            {thread.locked && <span className="status-label">已锁定</span>}
          </div>
          <h1>{thread.title}</h1>
          <p className="muted">
            {thread.author_name} · {beijingTime(thread.created_at)}（北京时间）
          </p>
        </header>
        {thread.hidden && <p>此讨论已隐藏。</p>}
        <SafeMarkdown>{thread.body}</SafeMarkdown>
        {writable && (thread.is_mine || thread.can_moderate) && (
          <Moderation
            key={`thread-${thread.revision}`}
            thread={thread}
            reload={() => q.refetch()}
          />
        )}
      </article>
      <h2>回复 · {thread.reply_count}</h2>
      {q.data.pages
        .flatMap((p) => p.replies)
        .map((r) => (
          <article className="panel stack" key={r.reply_id}>
            <p className="muted">
              {r.author_name} · {beijingTime(r.created_at)}
            </p>
            {r.hidden && <p>此回复已隐藏。</p>}
            <SafeMarkdown>{r.body}</SafeMarkdown>
            {writable && (r.is_mine || thread.can_moderate) && (
              <Moderation key={r.revision} thread={thread} reply={r} reload={() => q.refetch()} />
            )}
          </article>
        ))}
      {q.hasNextPage && (
        <Button
          variant="secondary"
          busy={q.isFetchingNextPage}
          onClick={() => void q.fetchNextPage()}
        >
          加载更多回复
        </Button>
      )}
      <p className="community-notice">
        请交流解题思路与调试方法，避免发布完整答案。每次发言至少间隔 10 秒。
      </p>
      {thread.locked && <p>讨论已锁定，暂不能回复。</p>}
      {course.data?.status === 'ARCHIVED' && <p>课程已归档，讨论只读。</p>}
      {course.isError && <p role="alert">{course.error.message}</p>}
      {writable && !thread.locked && !thread.hidden && (
        <form
          className="panel stack"
          onSubmit={(e) => {
            e.preventDefault()
            reply.mutate()
          }}
        >
          <TextArea
            label="回复正文"
            disabled={reply.isPending}
            required
            maxLength={4000}
            rows={5}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          {reply.error && <p role="alert">{reply.error.message}</p>}
          <Button type="submit" disabled={!body.trim()} busy={reply.isPending}>
            发布回复
          </Button>
        </form>
      )}
    </div>
  )
}
function Moderation({
  thread,
  reply,
  reload,
}: {
  thread: Thread
  reply?: Reply
  reload: () => Promise<unknown>
}) {
  const [reason, setReason] = useState('')
  const target = reply || thread
  const mutation = useMutation({
    mutationFn: async (change: Partial<ThreadChange>): Promise<Thread | Reply> =>
      reply
        ? communityApi.updateReply(reply.reply_id, {
            expected_revision: reply.revision,
            hidden: !reply.hidden,
            reason: reason.trim(),
          })
        : communityApi.update(thread.thread_id, {
            expected_revision: thread.revision,
            reason: reason.trim(),
            ...change,
          }),
    onSuccess: () => reload(),
  })
  if (reply?.hidden && !thread.can_moderate) return null
  return (
    <details className="community-management">
      <summary>管理{reply ? '回复' : '讨论'}</summary>
      <TextArea
        label="管理理由"
        hint="请输入 10—500 字理由，操作会记录审计。"
        minLength={10}
        maxLength={500}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <div className="button-row">
        {(!target.hidden || thread.can_moderate) && (
          <Button
            variant="secondary"
            busy={mutation.isPending}
            disabled={reason.trim().length < 10}
            onClick={() => mutation.mutate({ hidden: !target.hidden })}
          >
            {target.hidden ? '恢复内容' : '隐藏内容'}
          </Button>
        )}
        {!reply && (
          <>
            <Button
              variant="secondary"
              busy={mutation.isPending}
              disabled={reason.trim().length < 10}
              onClick={() => mutation.mutate({ resolved: !thread.resolved })}
            >
              {thread.resolved ? '标记未解决' : '标记已解决'}
            </Button>
            {thread.can_moderate && (
              <>
                <Button
                  variant="secondary"
                  busy={mutation.isPending}
                  disabled={reason.trim().length < 10}
                  onClick={() => mutation.mutate({ pinned: !thread.pinned })}
                >
                  {thread.pinned ? '取消置顶' : '置顶讨论'}
                </Button>
                <Button
                  variant="secondary"
                  busy={mutation.isPending}
                  disabled={reason.trim().length < 10}
                  onClick={() => mutation.mutate({ locked: !thread.locked })}
                >
                  {thread.locked ? '解除锁定' : '锁定讨论'}
                </Button>
              </>
            )}
          </>
        )}
      </div>
      {mutation.error && <p role="alert">{mutation.error.message}</p>}
    </details>
  )
}
