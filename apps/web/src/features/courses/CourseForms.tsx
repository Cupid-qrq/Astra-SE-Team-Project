import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'
import { DataTable } from '../../components/ui/DataTable'
import { StatePanel } from '../../components/ui/StatePanel'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import type { components } from '../../lib/api/schema'

export function CreateCourseForm() {
  const [title, setTitle] = useState('')
  const cache = useQueryClient()
  const mutation = useMutation({
    mutationFn: api.createCourse,
    onSuccess: () => {
      setTitle('')
      void cache.invalidateQueries({ queryKey: ['courses'] })
    },
  })
  function submit(event: FormEvent) {
    event.preventDefault()
    if (title.trim()) mutation.mutate({ title: title.trim() })
  }
  return (
    <form className="inline-form" onSubmit={submit}>
      <Field
        label="新课程名称"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        required
        maxLength={100}
      />
      <Button type="submit" busy={mutation.isPending}>
        创建课程
      </Button>
      {mutation.error && (
        <p role="alert" className="form-error">
          {mutation.error.message}
        </p>
      )}
      {mutation.isSuccess && <p role="status">课程已创建。</p>}
    </form>
  )
}

export function CourseManagement({ course }: { course: components['schemas']['Course'] }) {
  const [title, setTitle] = useState(course.title)
  const [revision, setRevision] = useState(course.revision)
  const [userId, setUserId] = useState('')
  const [pending, setPending] = useState<{ id: string; status: 'ACTIVE' | 'DISABLED' } | null>(null)
  const cache = useQueryClient()
  const members = useInfiniteQuery({
    queryKey: ['members', course.course_id],
    queryFn: ({ pageParam }) => api.members(course.course_id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
  })
  function refresh() {
    void cache.invalidateQueries({ queryKey: ['course', course.course_id] })
    void cache.invalidateQueries({ queryKey: ['courses'] })
    void cache.invalidateQueries({ queryKey: ['members', course.course_id] })
  }
  const rename = useMutation({
    mutationFn: () => api.updateCourse(course.course_id, { title, expected_revision: revision }),
    onSuccess: (value) => {
      setRevision(value.revision)
      refresh()
    },
  })
  const member = useMutation({
    mutationFn: (value: { id: string; status: 'ACTIVE' | 'DISABLED' }) =>
      api.updateMember(course.course_id, value.id, {
        status: value.status,
        expected_revision: revision,
      }),
    onSuccess: (value) => {
      setRevision(value.revision)
      setPending(null)
      setUserId('')
      refresh()
    },
  })
  const error = rename.error || member.error
  return (
    <section className="management-panel" aria-label="课程管理">
      <h2>课程管理</h2>
      <form
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault()
          rename.mutate()
        }}
      >
        <Field
          label="课程名称"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          maxLength={100}
        />
        <Button type="submit" busy={rename.isPending}>
          保存名称
        </Button>
      </form>
      {error && (
        <div role="alert" className="form-error">
          {error.message}
          <Button
            variant="quiet"
            onClick={async () => {
              const latest = await api.course(course.course_id)
              setRevision(latest.revision)
              rename.reset()
              member.reset()
              refresh()
            }}
          >
            重新读取版本，保留输入
          </Button>
        </div>
      )}
      <form
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault()
          member.mutate({ id: userId, status: 'ACTIVE' })
        }}
      >
        <Field
          label="学生账号编号"
          hint="使用管理员提供的学生 UUID 编号。"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          required
          pattern="[0-9a-fA-F-]{36}"
        />
        <Button type="submit" busy={member.isPending}>
          加入课程
        </Button>
      </form>
      {members.isPending ? (
        <StatePanel kind="loading" title="正在加载成员…" />
      ) : members.isError ? (
        <StatePanel
          kind="error"
          title="无法加载成员"
          description={members.error.message}
          onRetry={() => void members.refetch()}
        />
      ) : (
        <DataTable
          caption="课程成员"
          rows={members.data.pages.flatMap((p) => p.items)}
          rowKey={(m) => m.user_id}
          empty="暂无课程成员。"
          columns={[
            { key: 'name', heading: '学生', render: (m) => m.display_name },
            {
              key: 'status',
              heading: '状态',
              render: (m) => (m.status === 'ACTIVE' ? '在课' : '已停用'),
            },
            {
              key: 'action',
              heading: '操作',
              render: (m) => (
                <Button
                  variant="quiet"
                  onClick={() =>
                    setPending({
                      id: m.user_id,
                      status: m.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE',
                    })
                  }
                >
                  {m.status === 'ACTIVE' ? '停用成员' : '恢复成员'}
                </Button>
              ),
            },
          ]}
        />
      )}
      {members.hasNextPage && (
        <Button onClick={() => void members.fetchNextPage()} busy={members.isFetchingNextPage}>
          加载更多成员
        </Button>
      )}
      <ConfirmDialog
        open={!!pending}
        title="确认成员状态变更"
        description="变更影响该学生的课程访问和计分成员范围，历史记录保留。"
        confirmLabel="确认变更"
        busy={member.isPending}
        onCancel={() => setPending(null)}
        onConfirm={() => pending && member.mutate(pending)}
      />
    </section>
  )
}
