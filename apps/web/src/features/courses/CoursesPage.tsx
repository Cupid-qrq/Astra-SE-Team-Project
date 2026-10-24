import { useInfiniteQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Search } from 'lucide-react'
import { api } from '../../app/runtime'
import { DataTable } from '../../components/ui/DataTable'
import { StatePanel } from '../../components/ui/StatePanel'
import { Button } from '../../components/ui/Button'

export function CoursesPage() {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('ALL')
  const query = useInfiniteQuery({
    queryKey: ['courses'],
    queryFn: ({ pageParam }) => api.courses(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
  })
  const courses = query.data?.pages.flatMap((page) => page.items) || []
  const rows = courses.filter(
    (course) =>
      course.title.toLocaleLowerCase().includes(search.toLocaleLowerCase()) &&
      (filter === 'ALL' || filter === course.status),
  )
  return (
    <>
      <header className="page-heading">
        <div>
          <h1>我的课程</h1>
          <p>在这里继续学习，查看课程与作业。</p>
        </div>
        <span className="quiet-note">一步一步，学有所获。</span>
      </header>
      <section className="course-section" aria-label="课程列表">
        <div className="list-toolbar">
          <div className="filters" role="group" aria-label="课程状态">
            {[
              ['ALL', '全部课程'],
              ['ACTIVE', '进行中'],
              ['ARCHIVED', '已归档'],
            ].map(([value, label]) => (
              <button
                type="button"
                key={value}
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>
          <label className="search-field">
            <Search size={17} aria-hidden="true" />
            <span className="sr-only">搜索课程</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索课程"
            />
          </label>
        </div>
        {query.isPending ? (
          <StatePanel kind="loading" title="正在加载课程…" />
        ) : query.isError ? (
          <StatePanel
            kind="error"
            title="暂时无法加载课程"
            description={query.error.message}
            onRetry={() => void query.refetch()}
          />
        ) : (
          <DataTable
            caption="我的课程"
            rows={rows}
            rowKey={(row) => row.course_id}
            empty={
              search || filter !== 'ALL'
                ? '没有匹配的课程，请调整搜索内容。'
                : '暂未加入课程，请联系任课教师。'
            }
            columns={[
              {
                key: 'title',
                heading: '课程名称',
                render: (row) => (
                  <Link className="course-link" to={`/courses/${row.course_id}`}>
                    <span className="course-monogram" aria-hidden="true">
                      {row.title.slice(0, 1)}
                    </span>
                    <span>{row.title}</span>
                    <ArrowUpRight size={16} aria-hidden="true" />
                  </Link>
                ),
              },
              {
                key: 'status',
                heading: '课程状态',
                render: (row) => (
                  <span
                    className={`status-label ${row.status === 'ACTIVE' ? 'status-label--active' : ''}`}
                  >
                    <span aria-hidden="true">●</span>{' '}
                    {row.status === 'ACTIVE' ? '进行中' : '已归档'}
                  </span>
                ),
              },
            ]}
          />
        )}
        {query.hasNextPage && (
          <Button
            variant="secondary"
            busy={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >
            加载更多课程
          </Button>
        )}
        <p className="table-footnote">
          {courses.length ? `已加载 ${courses.length} 门课程` : '课程会在加入后显示'}
          {query.hasNextPage ? ' · 搜索仅筛选已加载课程' : ''}
        </p>
      </section>
      <footer className="workspace-footer">
        <span>Astra</span>
        <span>专注思考，持续进步。</span>
      </footer>
    </>
  )
}
