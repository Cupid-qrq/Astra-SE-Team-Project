import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, sessionKey } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { TextArea } from '../../components/ui/TextArea'
import { StatePanel } from '../../components/ui/StatePanel'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { downloadText } from '../assignments/drafts'
import { beijingTime } from '../assignments/time'

export function GradePage() {
  const { id = '' } = useParams()
  const cache = useQueryClient()
  const [reason, setReason] = useState('')
  const [cursor, setCursor] = useState<string | undefined>()
  const [command, setCommand] = useState<{ expected_revision: number; reason: string } | null>(null)
  const session = useQuery({ queryKey: sessionKey, queryFn: api.session })
  const grades = useQuery({
    queryKey: ['grades', id, cursor],
    queryFn: () => api.grades(id, cursor),
  })
  const publish = useMutation({
    mutationFn: () => api.publishGrades(id, command!),
    onSuccess: async () => {
      setCommand(null)
      await cache.invalidateQueries({ queryKey: ['grades', id] })
    },
  })
  const exportCsv = useMutation({
    mutationFn: () => api.exportGrades(id, grades.data!.grade_version!),
    onSuccess: (text) => downloadText(`astra-grades-${grades.data!.grade_version}.csv`, text),
  })
  if (grades.isPending) return <StatePanel kind="loading" title="正在计算成绩…" />
  if (grades.isError)
    return (
      <StatePanel
        kind="error"
        title="成绩暂不可用"
        description={grades.error.message}
        onRetry={() => void grades.refetch()}
      />
    )
  const value = grades.data
  const teacher = session.data?.user?.role === 'TEACHER'
  return (
    <>
      <Link to={`/assignments/${id}`}>返回作业</Link>
      <h1>作业成绩</h1>
      <p role="status">
        {value.state === 'PUBLISHED'
          ? '已发布成绩'
          : value.state === 'REJUDGING'
            ? '重评中'
            : '暂定成绩'}
      </p>
      {value.published_at && <p>发布于 {beijingTime(value.published_at)}</p>}
      {value.grade_version && <p className="template-text">成绩版本 {value.grade_version}</p>}
      {!value.students.length && <StatePanel kind="empty" title="暂无在课学生成绩" />}
      {value.students.map((student) => (
        <section className="panel stack" key={student.student_id} aria-label="学生成绩">
          {teacher && <p className="template-text">学生 {student.student_id}</p>}
          <h2>总分 {student.total}</h2>
          <p>{student.state === 'PENDING' ? '待处理，暂不能发布' : '计算完成'}</p>
          <ul className="resource-list">
            {student.items.map((item, index) => (
              <li key={item.problem_id}>
                <Link to={`/assignments/${id}/problems/${item.problem_id}`}>题目 {index + 1}</Link>
                <strong>
                  {item.score} / {item.points} 分
                </strong>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {cursor && <Button onClick={() => setCursor(undefined)}>返回成绩首页</Button>}
      {value.next_cursor && (
        <Button onClick={() => setCursor(value.next_cursor!)}>下一页成绩</Button>
      )}
      {teacher && (
        <section className="panel stack">
          <TextArea
            label="成绩发布理由"
            hint="请填写 10–500 字的发布理由。"
            minLength={10}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={500}
          />
          <Button
            disabled={[...reason.trim()].length < 10 || value.state === 'PUBLISHED'}
            onClick={() =>
              setCommand({ expected_revision: value.assignment_revision, reason: reason.trim() })
            }
          >
            发布成绩
          </Button>
          {value.grade_version && (
            <Button busy={exportCsv.isPending} onClick={() => exportCsv.mutate()}>
              导出当前成绩CSV
            </Button>
          )}
          {exportCsv.error && <p role="alert">{exportCsv.error.message}</p>}
        </section>
      )}
      <ConfirmDialog
        open={!!command}
        title="确认发布成绩"
        description="发布将冻结整个作业的成绩快照。服务端会复核截止、评测和公平事项。"
        confirmLabel="确认发布"
        onCancel={() => setCommand(null)}
        onConfirm={() => publish.mutate()}
        busy={publish.isPending}
      >
        {publish.error && <p role="alert">{publish.error.message}</p>}
      </ConfirmDialog>
    </>
  )
}
