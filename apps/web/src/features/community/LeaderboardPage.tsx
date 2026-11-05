import { useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api, sessionKey } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { DataTable } from '../../components/ui/DataTable'
import { StatePanel } from '../../components/ui/StatePanel'
import { beijingTime } from '../assignments/time'
import { communityApi } from './communityApi'
export function LeaderboardPage() {
  const { id = '' } = useParams()
  const [kind, setKind] = useState<'progress' | 'grades'>('progress')
  const client = useQueryClient()
  const session = useQuery({ queryKey: sessionKey, queryFn: api.session })
  const course = useQuery({ queryKey: ['course', id], queryFn: () => api.course(id) })
  const board = useInfiniteQuery({
    queryKey: ['leaderboard', id, kind],
    queryFn: ({ pageParam }) => communityApi.leaderboard(id, kind, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
  })
  const preference = useMutation({
    mutationFn: (show: boolean) => communityApi.preference(id, show),
    onSuccess: () => client.invalidateQueries({ queryKey: ['leaderboard', id] }),
  })
  const first = board.data?.pages[0]
  return (
    <div className="community-page stack">
      <Link className="back-link" to={`/courses/${id}`}>
        ← 返回课程
      </Link>
      <header className="page-heading">
        <div>
          <h1>课程排行榜</h1>
          <p>{course.data?.title || '本课程'} · 同分并列，不以提交速度打破平局</p>
        </div>
      </header>
      <div className="button-row" aria-label="榜单类型">
        <Button
          variant={kind === 'progress' ? 'primary' : 'secondary'}
          aria-pressed={kind === 'progress'}
          onClick={() => setKind('progress')}
        >
          正式作业通过题数
        </Button>
        <Button
          variant={kind === 'grades' ? 'primary' : 'secondary'}
          aria-pressed={kind === 'grades'}
          onClick={() => setKind('grades')}
        >
          已发布成绩累计
        </Button>
      </div>
      <p className="community-notice">
        {kind === 'progress'
          ? '统计已开放、已发布作业中当前有效的正式通过题数；按作业与题目去重，不计练习、旧轮次及系统错误。'
          : '累计当前有效的已发布成绩；重评中、公平复核待裁决及轮次不匹配的作业暂不计入。'}
      </p>
      <p>默认匿名。选择显示姓名后，本课程同学可在榜单看到你的姓名；任课教师可识别学生。</p>
      {first && (
        <p className="muted">
          计入 {first.included_assignments} 份作业 · 更新于 {beijingTime(first.updated_at)}
          （北京时间）
        </p>
      )}
      {session.data?.user?.role === 'STUDENT' && first && course.data?.status === 'ACTIVE' && (
        <label className="community-preference">
          <input
            type="checkbox"
            checked={first.show_name}
            disabled={preference.isPending}
            onChange={(e) => preference.mutate(e.target.checked)}
          />
          在本课程榜单显示我的姓名
        </label>
      )}
      {preference.error && <p role="alert">{preference.error.message}</p>}
      {course.data?.status === 'ARCHIVED' && <p>课程已归档，榜单偏好只读。</p>}
      {board.isPending ? (
        <StatePanel kind="loading" title="正在读取榜单…" />
      ) : board.isError ? (
        <StatePanel
          kind="error"
          title="榜单暂不可用"
          description={board.error.message}
          onRetry={() => void board.refetch()}
        />
      ) : (
        <DataTable
          caption={kind === 'progress' ? '正式作业通过题数榜' : '已发布成绩累计榜'}
          rows={board.data.pages.flatMap((p) => p.items)}
          rowKey={(r) => r.entry_id}
          empty="暂无可展示的学生记录。"
          columns={[
            { key: 'rank', heading: '名次', render: (r) => r.rank },
            {
              key: 'name',
              heading: '学生',
              render: (r) => (
                <>
                  <span>{r.display_name}</span>
                  {r.is_me && <span className="status-label">我</span>}
                </>
              ),
            },
            {
              key: 'value',
              heading: kind === 'progress' ? '通过题数' : '累计分数',
              render: (r) => r.value,
            },
          ]}
        />
      )}
      {board.hasNextPage && (
        <Button
          variant="secondary"
          busy={board.isFetchingNextPage}
          onClick={() => void board.fetchNextPage()}
        >
          加载更多排名
        </Button>
      )}
    </div>
  )
}
