import { useMutation, useQuery, useInfiniteQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { TextArea } from '../../components/ui/TextArea'
import { Field } from '../../components/ui/Field'
import { StatePanel } from '../../components/ui/StatePanel'
import type { components } from '../../lib/api/schema'

export function TeacherOperations() {
  const { id = '' } = useParams()
  const assignment = useQuery({ queryKey: ['assignment', id], queryFn: () => api.assignment(id) })
  const incidents = useInfiniteQuery({
    queryKey: ['incidents'],
    queryFn: ({ pageParam }) => api.incidents(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
  })
  const [problem, setProblem] = useState('')
  const [version, setVersion] = useState('')
  const [reason, setReason] = useState('')
  const [batchId, setBatchId] = useState('')
  const [preview, setPreview] = useState<components['schemas']['RejudgePreview'] | null>(null)
  const versions = useQuery({
    queryKey: ['versions', problem],
    queryFn: () => api.versions(problem),
    enabled: !!problem,
  })
  const batch = useQuery({
    queryKey: ['rejudge', batchId],
    queryFn: () => api.rejudge(batchId),
    enabled: !!batchId,
    refetchInterval: (q) =>
      q.state.data && ['ACTIVE', 'CANCELLED', 'READY', 'FAILED'].includes(q.state.data.state)
        ? false
        : 3000,
  })
  const action = useMutation({
    mutationFn: async (command: string) => {
      const revision = assignment.data!.revision
      if (command === 'preview')
        setPreview(
          await api.rejudgePreview(id, {
            problem_id: problem,
            new_version_id: version,
            expected_revision: revision,
          }),
        )
      if (command === 'create') {
        const created = await api.createRejudge(id, {
          new_version_id: version,
          range_checksum: preview!.range_checksum,
          expected_revision: revision,
          reason,
        })
        setBatchId(created.batch_id)
        setPreview(null)
      }
      if (command === 'activate')
        await api.activateRejudge(batchId, {
          expected_batch_revision: batch.data!.revision,
          expected_assignment_revision: batch.data!.assignment_revision,
          reason,
        })
      if (command === 'cancel')
        await api.cancelRejudge(batchId, { expected_revision: batch.data!.revision, reason })
      await assignment.refetch()
      if (batchId) await batch.refetch()
    },
  })
  const decision = useMutation({
    mutationFn: ({
      incident_id,
      decision,
    }: {
      incident_id: string
      decision: 'EXTEND' | 'NO_IMPACT'
    }) =>
      api.decideFairness(id, {
        incident_id,
        decision,
        reason,
        expected_revision: assignment.data!.revision,
      }),
    onSuccess: async () => {
      await assignment.refetch()
      await incidents.refetch()
    },
  })
  if (assignment.isPending) return <StatePanel kind="loading" title="正在读取作业…" />
  if (assignment.isError)
    return <StatePanel kind="error" title="作业不可用" description={assignment.error.message} />
  return (
    <>
      <Link to={`/assignments/${id}`}>返回作业</Link>
      <h1>重评与公平处理</h1>
      <TextArea
        label="操作理由"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        maxLength={500}
      />
      <section className="panel stack">
        <h2>统一重评</h2>
        <label>
          重评题目
          <select
            value={problem}
            onChange={(event) => {
              setProblem(event.target.value)
              setVersion('')
              setPreview(null)
            }}
          >
            <option value="">请选择</option>
            {assignment.data.items.map((item) => (
              <option key={item.problem_id} value={item.problem_id}>
                {item.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          目标版本
          <select
            value={version}
            onChange={(event) => {
              setVersion(event.target.value)
              setPreview(null)
            }}
          >
            <option value="">请选择已发布版本</option>
            {versions.data?.items
              .filter((row) => row.published_at)
              .map((row) => (
                <option key={row.version_id} value={row.version_id}>
                  版本 {row.revision} · {row.title}
                </option>
              ))}
          </select>
        </label>
        <Button
          onClick={() => action.mutate('preview')}
          busy={action.isPending}
          disabled={!version}
        >
          预览全部影响范围
        </Button>
        {preview && (
          <>
            <p>
              将重评 {preview.affected_count} 份正式提交，语言 {preview.languages.join('、')}。
            </p>
            <Button
              onClick={() => action.mutate('create')}
              busy={action.isPending}
              disabled={!reason.trim()}
            >
              确认创建全量重评
            </Button>
          </>
        )}
        <Field
          label="已有批次编号"
          value={batchId}
          onChange={(event) => setBatchId(event.target.value)}
        />
        {batch.data && (
          <>
            {batch.data.differences.map((row) => (
              <p className="template-text" key={row.student_id}>
                学生 {row.student_id}：{row.before} → {row.after}（{row.delta > 0 ? '+' : ''}
                {row.delta}）
              </p>
            ))}
            <p role="status">
              {batch.data.state} · 已完成 {batch.data.finished_count} / {batch.data.affected_count}{' '}
              · 平台故障 {batch.data.failed_count}
            </p>
            <Button
              disabled={batch.data.state !== 'READY' || !reason.trim()}
              onClick={() => action.mutate('activate')}
              busy={action.isPending}
            >
              确认整批激活新成绩
            </Button>
            <Button
              disabled={['ACTIVE', 'CANCELLED'].includes(batch.data.state) || !reason.trim()}
              onClick={() => action.mutate('cancel')}
              busy={action.isPending}
            >
              取消未激活重评
            </Button>
          </>
        )}
        {(action.error || batch.error) && (
          <p role="alert">{action.error?.message || batch.error?.message}</p>
        )}
      </section>
      <section className="panel stack">
        <h2>公平事件裁决</h2>
        {incidents.data?.pages
          .flatMap((page) => page.items)
          .filter((event) => event.assignments.some((row) => row.assignment_id === id))
          .map((event) => (
            <article key={event.incident_id}>
              <p className="template-text">
                事件 {event.incident_id} · {event.reason_code}
              </p>
              <p>
                {event.recovered_at ? '已恢复' : '等待恢复登记'} ·{' '}
                {event.assignments.find((row) => row.assignment_id === id)?.decision}
              </p>
              <Button
                disabled={!reason.trim() || !event.recovered_at}
                busy={decision.isPending}
                onClick={() =>
                  decision.mutate({ incident_id: event.incident_id, decision: 'EXTEND' })
                }
              >
                确认全班统一延期
              </Button>
              <Button
                disabled={!reason.trim() || !event.recovered_at}
                busy={decision.isPending}
                onClick={() =>
                  decision.mutate({ incident_id: event.incident_id, decision: 'NO_IMPACT' })
                }
              >
                确认无影响
              </Button>
            </article>
          ))}
        {decision.error && <p role="alert">{decision.error.message}</p>}
        {incidents.hasNextPage && (
          <Button
            busy={incidents.isFetchingNextPage}
            onClick={() => void incidents.fetchNextPage()}
          >
            加载更多公平事件
          </Button>
        )}
        {incidents.isError && <p role="alert">{incidents.error.message}</p>}
      </section>
    </>
  )
}
