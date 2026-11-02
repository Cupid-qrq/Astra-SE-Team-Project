import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { api, sessionKey } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { StatePanel } from '../../components/ui/StatePanel'
import { beijingTime } from '../assignments/time'
import { HintWorkspace } from './HintWorkspace'

export default function LearningPage() {
  const session = useQuery({ queryKey: sessionKey, queryFn: api.session })
  const [params] = useSearchParams()
  const courseId = params.get('course_id') || undefined
  const user = session.data?.user
  if (user?.role !== 'STUDENT')
    return <StatePanel kind="forbidden" title="仅学生可查看个人学习记录" />
  return (
    <StudentLearning
      key={user.user_id + ':' + (courseId ?? '')}
      courseId={courseId}
      ownerId={user.user_id}
      submissionId={params.get('submission_id') || undefined}
    />
  )
}
function StudentLearning({
  courseId,
  ownerId,
  submissionId,
}: {
  courseId?: string
  ownerId: string
  submissionId?: string
}) {
  const [context, setContext] = useState<'FORMAL' | 'PRACTICE'>('FORMAL')
  const [source, setSource] = useState(submissionId)
  const review = useInfiniteQuery({
    queryKey: ['reviewItems', courseId, context],
    queryFn: ({ pageParam }) => api.reviewItems(context, courseId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
  })
  const recommendations = useQuery({
    queryKey: ['recommendations', courseId],
    queryFn: () => api.recommendations(courseId),
  })
  return (
    <div className="learning-page stack">
      {courseId && (
        <Link className="back-link" to={`/courses/${courseId}`}>
          ← 返回课程
        </Link>
      )}
      <header className="page-heading">
        <div>
          <h1>{courseId ? '本课学习记录' : '我的学习'}</h1>
          <p>回顾错题，查看推荐练习和本人提交的提示。</p>
        </div>
      </header>
      <section className="panel stack" aria-label="错题记录">
        <h2>错题记录</h2>
        <label className="field">
          提交类别
          <select value={context} onChange={(e) => setContext(e.target.value as typeof context)}>
            <option value="FORMAL">正式提交</option>
            <option value="PRACTICE">练习提交</option>
          </select>
        </label>
        {review.isPending ? (
          <StatePanel kind="loading" title="正在读取错题…" />
        ) : review.isError ? (
          <StatePanel
            kind="error"
            title="错题记录暂不可用"
            description={review.error.message}
            onRetry={() => void review.refetch()}
          />
        ) : (
          <>
            {review.data.pages[0].items.length === 0 ? (
              <p>此类别暂无待复习的错题。</p>
            ) : (
              <ul className="resource-list">
                {review.data.pages
                  .flatMap((p) => p.items)
                  .map((item) => (
                    <li key={item.submission_id}>
                      <Link to={`/assignments/${item.assignment_id}/problems/${item.problem_id}`}>
                        {item.title}
                      </Link>
                      <span>
                        {item.verdict} · {beijingTime(item.accepted_at)}（北京时间）
                      </span>
                      <a href="#learning-hints" onClick={() => setSource(item.submission_id)}>
                        为此提交请求提示
                      </a>
                    </li>
                  ))}
              </ul>
            )}
            {review.hasNextPage && (
              <Button
                variant="secondary"
                busy={review.isFetchingNextPage}
                onClick={() => void review.fetchNextPage()}
              >
                加载更多错题
              </Button>
            )}
          </>
        )}
      </section>
      <section className="panel stack" aria-label="推荐练习">
        <h2>推荐练习</h2>
        {recommendations.isPending ? (
          <StatePanel kind="loading" title="正在读取推荐…" />
        ) : recommendations.isError ? (
          <StatePanel
            kind="error"
            title="推荐练习暂不可用"
            description={recommendations.error.message}
            onRetry={() => void recommendations.refetch()}
          />
        ) : recommendations.data.items.length === 0 ? (
          <p>暂无符合条件的练习</p>
        ) : (
          <ul className="resource-list">
            {recommendations.data.items.map((item) => (
              <li key={item.problem_id}>
                <Link to={`/practice-problems/${item.problem_id}`}>{item.title}</Link>
                <span>{item.tags.join(' · ')}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <div id="learning-hints">
        <HintWorkspace ownerId={ownerId} submissionId={source} />
      </div>
    </div>
  )
}
