import { verdictLabels } from './resultLabels'
import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { StatePanel } from '../../components/ui/StatePanel'
import { FixedHelp } from '../learning/FixedHelp'
import type { components } from '../../lib/api/schema'
import type { ResultProps } from '../integrations/teaching'

export type Submission = components['schemas']['SubmissionView']

const states = {
  QUEUED: '等待评测',
  RUNNING: '正在评测',
  RETRY_WAIT: '等待重试',
  FINISHED: '评测完成',
}
type Summary = Pick<
  Submission,
  'state' | 'verdict' | 'mode' | 'generation' | 'time_ms' | 'memory_bytes' | 'case_results'
>
export function ResultSummary({ value }: { value: Summary }) {
  return (
    <section className="panel stack" aria-label="评测结果">
      <p role="status">{states[value.state]}</p>
      <p>{value.mode === 'FORMAL' ? '正式提交' : '练习提交'}</p>
      <p>第 {value.generation} 轮</p>
      {value.verdict && <h3>{verdictLabels[value.verdict]}</h3>}
      {value.verdict === 'SE' && <p>本次遇到平台故障，请保留提交编号并查看平台通知。</p>}
      <p>
        CPU {value.time_ms === null ? '未知' : `${value.time_ms} ms`} · 内存{' '}
        {value.memory_bytes === null ? '未知' : `${Math.ceil(value.memory_bytes / 1024)} KiB`}
      </p>
      {value.case_results.length > 0 && (
        <ul className="resource-list">
          {value.case_results.map((point) => (
            <li key={point.order}>
              <span>测试点 {point.order}</span>
              <strong>{verdictLabels[point.verdict]}</strong>
              <span>CPU {point.cpu_ms === null ? '未知' : `${point.cpu_ms} ms`}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
export function SubmissionContent({ submissionId }: { submissionId: string }) {
  const result = useQuery({
    queryKey: ['submission', submissionId],
    queryFn: () => api.submission(submissionId),
    refetchInterval: (query) =>
      query.state.status === 'error' || query.state.data?.state === 'FINISHED' ? false : 2000,
  })
  const feedback = useQuery({
    queryKey: ['submission-feedback', submissionId, result.data?.attempt_id],
    queryFn: async () => {
      const value = await api.submissionFeedback(submissionId)
      if (value.feedback_version_id !== result.data?.feedback_version_id) {
        void result.refetch()
        throw new Error('评测轮次已更新，正在重新核对结果，请稍后重试帮助。')
      }
      return value
    },
    enabled: !!result.data?.feedback_version_id && result.data.state === 'FINISHED',
  })
  if (result.isPending) return <StatePanel kind="loading" title="正在读取结果…" />
  if (result.isError)
    return (
      <StatePanel
        kind="error"
        title="暂时无法读取结果"
        description={result.error.message}
        onRetry={() => void result.refetch()}
      />
    )
  return (
    <>
      <ResultSummary value={result.data} />
      <FixedHelp
        state={result.data.state}
        verdict={result.data.verdict}
        value={
          feedback.data?.feedback_version_id === result.data.feedback_version_id
            ? feedback.data
            : undefined
        }
        loading={feedback.isFetching}
        error={feedback.error?.message}
      />
      {feedback.isError && (
        <Button onClick={() => void feedback.refetch()} busy={feedback.isFetching}>
          重新读取本轮帮助
        </Button>
      )}
      <Link to={`/submissions/${submissionId}`}>查看提交详情与轮次</Link>
    </>
  )
}
export function SubmissionResult({ submissionId, onClose }: ResultProps) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const element = dialog.current
    const previous = document.activeElement as HTMLElement | null
    element?.showModal()
    return () => {
      element?.close()
      previous?.focus()
    }
  }, [])
  return (
    <dialog
      ref={dialog}
      className="dialog submission-dialog"
      aria-label="提交评测结果"
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
    >
      <Button onClick={onClose}>关闭结果</Button>
      <h2>提交评测结果</h2>
      <SubmissionContent submissionId={submissionId} />
    </dialog>
  )
}
