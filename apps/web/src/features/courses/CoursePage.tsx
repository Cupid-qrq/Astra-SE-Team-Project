import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api, sessionKey } from '../../app/runtime'
import { CourseManagement } from './CourseForms'
import { DataTable } from '../../components/ui/DataTable'
import { StatePanel } from '../../components/ui/StatePanel'
import { Button } from '../../components/ui/Button'

const states = {
  DRAFT: '草稿',
  SCHEDULED: '未开放',
  OPEN: '进行中',
  CLOSED: '已截止',
  ARCHIVED: '已归档',
}
export function CoursePage() {
  const session = useQuery({ queryKey: sessionKey, queryFn: api.session })
  const { id = '' } = useParams()
  const course = useQuery({ queryKey: ['course', id], queryFn: () => api.course(id) })
  const assignments = useInfiniteQuery({
    queryKey: ['assignments', id],
    queryFn: ({ pageParam }) => api.assignments(id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
  })
  if (course.isPending) return <StatePanel kind="loading" title="正在加载课程…" />
  if (course.isError)
    return (
      <StatePanel
        kind="error"
        title="课程暂不可用"
        description={course.error.message}
        onRetry={() => void course.refetch()}
      />
    )
  return (
    <>
      <Link className="back-link" to="/courses">
        ← 我的课程
      </Link>
      <header className="page-heading">
        <div>
          <h1>{course.data.title}</h1>
          <p>课程作业与学习安排</p>
        </div>
        <span className="status-label">
          {course.data.status === 'ACTIVE' ? '进行中' : '已归档'}
        </span>
      </header>
      {session.data?.user?.role === 'TEACHER' && course.data.status === 'ACTIVE' && (
        <CourseManagement key={id} course={course.data} />
      )}
      <h2 className="section-title">课程作业</h2>
      {assignments.isPending ? (
        <StatePanel kind="loading" title="正在加载作业…" />
      ) : assignments.isError ? (
        <StatePanel
          kind="error"
          title="作业暂不可用"
          description={assignments.error.message}
          onRetry={() => void assignments.refetch()}
        />
      ) : (
        <DataTable
          caption="课程作业"
          rows={assignments.data.pages.flatMap((page) => page.items)}
          rowKey={(row) => row.assignment_id}
          empty="暂无已发布的作业。"
          columns={[
            { key: 'title', heading: '作业名称', render: (row) => row.title },
            { key: 'state', heading: '状态', render: (row) => states[row.state] },
            {
              key: 'due',
              heading: '截止时间（北京时间）',
              render: (row) =>
                new Intl.DateTimeFormat('zh-CN', {
                  timeZone: 'Asia/Shanghai',
                  month: '2-digit',
                  day: '2-digit',
                  hour: '2-digit',
                  minute: '2-digit',
                  hour12: false,
                }).format(new Date(row.due_at)),
            },
          ]}
        />
      )}
      {assignments.hasNextPage && (
        <Button
          variant="secondary"
          onClick={() => void assignments.fetchNextPage()}
          busy={assignments.isFetchingNextPage}
        >
          加载更多作业
        </Button>
      )}
    </>
  )
}
