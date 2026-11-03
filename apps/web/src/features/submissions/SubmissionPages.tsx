import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { StatePanel } from '../../components/ui/StatePanel'
import { TextArea } from '../../components/ui/TextArea'
import { beijingTime } from '../assignments/time'
import { SubmissionContent } from './SubmissionResult'
import { verdictLabels } from './resultLabels'

export function SubmissionPage() {
  const { id = '' } = useParams()
  const result = useQuery({ queryKey: ['submission', id], queryFn: () => api.submission(id) })
  const rounds = useInfiniteQuery({
    queryKey: ['submission-attempts', id, result.data?.generation],
    queryFn: ({ pageParam }) => api.submissionAttempts(id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
  })
  return (
    <>
      <h1>提交详情</h1>
      <SubmissionContent submissionId={id} />
      {result.data && (
        <>
          <p>受理于 {beijingTime(result.data.accepted_at)}</p>
          <p>语言 {result.data.language_key}</p>
          <Link to={`/assignments/${result.data.assignment_id}/submissions`}>返回提交历史</Link>
          <TextArea label="本次提交源码" value={result.data.code} readOnly rows={12} />
          <h2>评测轮次</h2>
          {rounds.isError && (
            <StatePanel
              kind="error"
              title="轮次读取失败"
              description={rounds.error.message}
              onRetry={() => void rounds.refetch()}
            />
          )}
          <ul className="resource-list">
            {rounds.data?.pages
              .flatMap((page) => page.items)
              .map((round) => (
                <li key={round.attempt_id}>
                  <span>第 {round.generation} 轮</span>
                  <strong>{round.verdict ? verdictLabels[round.verdict] : '处理中'}</strong>
                  <span>{round.reason_code}</span>
                </li>
              ))}
          </ul>
          {rounds.hasNextPage && (
            <Button onClick={() => void rounds.fetchNextPage()} busy={rounds.isFetchingNextPage}>
              加载更多轮次
            </Button>
          )}
        </>
      )}
    </>
  )
}
export function SubmissionHistoryPage() {
  const { id = '' } = useParams()
  const [problem, setProblem] = useState('')
  const [verdict, setVerdict] = useState<'' | 'AC' | 'WA' | 'CE' | 'TLE' | 'RE' | 'SE'>('')
  const assignment = useQuery({ queryKey: ['assignment', id], queryFn: () => api.assignment(id) })
  const history = useInfiniteQuery({
    queryKey: ['submissions', id, problem, verdict],
    queryFn: ({ pageParam }) =>
      api.submissions(id, problem || undefined, verdict || undefined, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
  })
  return (
    <>
      <Link to={`/assignments/${id}`}>返回作业</Link>
      <h1>提交历史</h1>
      <div className="list-toolbar">
        <label>
          筛选题目
          <select value={problem} onChange={(event) => setProblem(event.target.value)}>
            <option value="">全部题目</option>
            {assignment.data?.items.map((item) => (
              <option key={item.problem_id} value={item.problem_id}>
                {item.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          筛选判定
          <select
            value={verdict}
            onChange={(event) => setVerdict(event.target.value as typeof verdict)}
          >
            <option value="">全部判定</option>
            {(['AC', 'WA', 'CE', 'TLE', 'RE', 'SE'] as const).map((value) => (
              <option key={value} value={value}>
                {verdictLabels[value]}
              </option>
            ))}
          </select>
        </label>
      </div>
      {history.isPending ? (
        <StatePanel kind="loading" title="正在读取提交历史…" />
      ) : history.isError ? (
        <StatePanel
          kind="error"
          title="提交历史不可用"
          description={history.error.message}
          onRetry={() => void history.refetch()}
        />
      ) : (
        <>
          {!history.data.pages.some((page) => page.items.length) && (
            <StatePanel kind="empty" title="暂无符合条件的提交" />
          )}
          <ul className="resource-list">
            {history.data.pages
              .flatMap((page) => page.items)
              .map((row) => (
                <li key={row.submission_id}>
                  <Link to={`/submissions/${row.submission_id}`}>
                    {beijingTime(row.accepted_at)} · {row.language_key}
                  </Link>
                  <span>{row.mode === 'FORMAL' ? '正式提交' : '练习提交'}</span>
                  <strong>{row.verdict ? verdictLabels[row.verdict] : '处理中'}</strong>
                </li>
              ))}
          </ul>
          {history.hasNextPage && (
            <Button onClick={() => void history.fetchNextPage()} busy={history.isFetchingNextPage}>
              加载更多提交
            </Button>
          )}
        </>
      )}
    </>
  )
}
