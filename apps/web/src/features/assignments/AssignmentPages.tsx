import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useState } from 'react'
import { api, sessionKey } from '../../app/runtime'
import { StatePanel } from '../../components/ui/StatePanel'
import { Field } from '../../components/ui/Field'
import { Button } from '../../components/ui/Button'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { AssignmentForm } from './AssignmentForm'
import { beijingTime, fromBeijing } from './time'
import type { components } from '../../lib/api/schema'

export function CreateAssignmentPage() {
  const { id = '' } = useParams()
  return (
    <>
      <Link to={`/courses/${id}`} className="back-link">
        ← 返回课程
      </Link>
      <h1>新建作业</h1>
      <AssignmentForm courseId={id} />
    </>
  )
}
export function AssignmentPage() {
  const { id = '' } = useParams()
  const session = useQuery({ queryKey: sessionKey, queryFn: api.session })
  const query = useQuery({
    queryKey: ['assignment', id],
    queryFn: () => api.assignment(id),
    refetchInterval: 30_000,
  })
  if (query.isPending) return <StatePanel kind="loading" title="正在读取作业…" />
  if (query.isError)
    return (
      <StatePanel
        kind="error"
        title="作业不可用"
        description={query.error.message}
        onRetry={() => void query.refetch()}
      />
    )
  const value = query.data
  const teacher = session.data?.user?.role === 'TEACHER'
  return (
    <>
      <Link to={`/courses/${value.course_id}`} className="back-link">
        ← 返回课程
      </Link>
      <header className="page-heading">
        <div>
          <h1>{value.title}</h1>
          <p>
            {beijingTime(value.open_at)} — {beijingTime(value.due_at)}（北京时间）
          </p>
        </div>
        <span className="status-label">
          {
            {
              DRAFT: '草稿',
              SCHEDULED: '未开放',
              OPEN: '进行中',
              CLOSED: '已截止',
              ARCHIVED: '已归档',
            }[value.state]
          }
        </span>
      </header>
      {teacher && value.state === 'DRAFT' && (
        <AssignmentForm
          key={id}
          courseId={value.course_id}
          existing={value}
          onSaved={() => void query.refetch()}
        />
      )}
      {value.state === 'SCHEDULED' && !teacher && (
        <StatePanel
          kind="empty"
          title="作业尚未开放"
          description="开放后可以查看题目并开始编程。"
        />
      )}
      <ul className="resource-list">
        {value.items.map((item) => (
          <li key={item.problem_id}>
            <strong>{item.title}</strong>
            <span>{item.points} 分</span>
            <Link to={`/assignments/${id}/problems/${item.problem_id}`}>
              {teacher ? '查看题目' : '开始编程'}
            </Link>
          </li>
        ))}
      </ul>
      {value.state === 'CLOSED' && <p>正式提交已截止，后续提交仅用于练习。</p>}
      {teacher && value.state !== 'ARCHIVED' && (
        <AssignmentActions value={value} reload={() => query.refetch()} />
      )}
    </>
  )
}
function AssignmentActions({
  value,
  reload,
}: {
  value: components['schemas']['AssignmentView']
  reload: () => Promise<unknown>
}) {
  const [reason, setReason] = useState('')
  const [due, setDue] = useState('')
  const [policy, setPolicy] = useState<'DISABLED' | 'GUIDED'>(value.ai_policy)
  const [action, setAction] = useState<'publish' | 'deadline' | 'policy' | null>(null)
  const mutation = useMutation({
    mutationFn: async (kind: 'publish' | 'deadline' | 'policy') => {
      const common = { expected_revision: value.revision, reason }
      if (kind === 'publish') return api.publishAssignment(value.assignment_id, common)
      if (kind === 'deadline')
        return api.extendAssignment(value.assignment_id, {
          ...common,
          new_due_at: fromBeijing(due),
        })
      return api.assignmentPolicy(value.assignment_id, { ...common, ai_policy: policy })
    },
    onSuccess: () => {
      setAction(null)
      void reload()
    },
  })
  const reasonValid = [...reason].length >= 10 && [...reason].length <= 500
  return (
    <section className="management-panel">
      <h2>{value.state === 'DRAFT' ? '发布确认' : '作业调整'}</h2>
      <Field
        label="操作理由"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        minLength={10}
        maxLength={500}
        hint="10—500 个字符，随操作记录保留。"
      />
      {value.state === 'DRAFT' ? (
        <Button disabled={!reasonValid} onClick={() => setAction('publish')}>
          发布作业
        </Button>
      ) : (
        <>
          <Field
            label="新的截止时间（北京时间）"
            type="datetime-local"
            value={due}
            onChange={(e) => setDue(e.target.value)}
          />
          <Button
            variant="secondary"
            disabled={!reasonValid || !due}
            onClick={() => setAction('deadline')}
          >
            统一延期
          </Button>
          <label className="field">
            新的提示策略
            <select
              value={policy}
              onChange={(e) => setPolicy(e.target.value as 'DISABLED' | 'GUIDED')}
            >
              <option value="DISABLED">关闭模型提示</option>
              <option
                value="GUIDED"
                disabled={value.state !== 'SCHEDULED' && value.ai_policy === 'DISABLED'}
              >
                允许引导提示
              </option>
            </select>
          </label>
          <Button variant="secondary" disabled={!reasonValid} onClick={() => setAction('policy')}>
            调整提示策略
          </Button>
        </>
      )}
      {mutation.error && (
        <p role="alert" className="form-error">
          {mutation.error.message}
        </p>
      )}
      {mutation.isSuccess && (
        <p role="status">
          {mutation.variables === 'publish' ? '作业已发布。' : '作业调整已保存。'}
        </p>
      )}
      <ConfirmDialog
        open={!!action}
        title={action === 'publish' ? '确认发布作业' : '确认调整作业'}
        description={`「${value.title}」修订 ${value.revision}，影响全班成员。${action === 'deadline' ? '延期不会追认过去的练习提交。' : '发布后题目和分值不可修改。'}${mutation.error?.message || ''}`}
        confirmLabel={action === 'publish' ? '确认发布' : '确认调整'}
        onCancel={() => setAction(null)}
        onConfirm={() => action && mutation.mutate(action)}
        busy={mutation.isPending}
      />
    </section>
  )
}
