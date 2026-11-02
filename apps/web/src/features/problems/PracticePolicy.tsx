import { useInfiniteQuery, useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { SafeMarkdown } from '../../components/ui/SafeMarkdown'
import { StatePanel } from '../../components/ui/StatePanel'
import type { components } from '../../lib/api/schema'

type Schema = components['schemas']
type Problem = Schema['ProblemPage']['items'][number]

export function PracticePolicy({ problem, saved }: { problem: Problem; saved: () => void }) {
  const [editing, setEditing] = useState(false)
  return editing ? (
    <PolicyForm problem={problem} close={() => setEditing(false)} saved={saved} />
  ) : (
    <Button variant="quiet" onClick={() => setEditing(true)}>
      调整练习开放策略
    </Button>
  )
}

function PolicyForm({
  problem,
  close,
  saved,
}: {
  problem: Problem
  close: () => void
  saved: () => void
}) {
  const [base] = useState(problem)
  const [version, setVersion] = useState(base.practice_version_id || '')
  const [family, setFamily] = useState(base.canonical_problem_id)
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState<Schema['PracticePolicy'] | null>(null)
  const versions = useInfiniteQuery({
    queryKey: ['versions', base.problem_id],
    queryFn: ({ pageParam }) => api.versions(base.problem_id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
  })
  const mutation = useMutation({
    mutationFn: (body: Schema['PracticePolicy']) => api.practicePolicy(base.problem_id, body),
    onSuccess: () => {
      saved()
      close()
    },
    onError: () => setPending(null),
  })
  const options = versions.data?.pages.flatMap((p) => p.items).filter((v) => v.published_at) || []
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        setPending({
          expected_revision: base.revision,
          canonical_problem_id: family,
          practice_released: !!version,
          ...(version ? { practice_version_id: version } : {}),
          reason: reason.trim(),
        })
      }}
    >
      <h3>{base.title} · 练习开放策略</h3>
      <label>
        开放版本
        <select value={version} onChange={(e) => setVersion(e.target.value)}>
          <option value="">关闭练习</option>
          {version && !options.some((v) => v.version_id === version) && (
            <option value={version}>当前固定版本</option>
          )}
          {options.map((v) => (
            <option key={v.version_id} value={v.version_id}>
              {v.title} · {v.version_id}
            </option>
          ))}
        </select>
      </label>
      {versions.hasNextPage && (
        <Button type="button" onClick={() => void versions.fetchNextPage()}>
          加载更多版本
        </Button>
      )}
      {versions.isError && <p role="alert">{versions.error.message}</p>}
      <label>
        题目家族编号
        <input required value={family} onChange={(e) => setFamily(e.target.value)} />
      </label>
      <label>
        调整理由
        <textarea required value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      {mutation.error && <p role="alert">{mutation.error.message}</p>}
      <Button
        type="submit"
        disabled={!family || [...reason.trim()].length < 10 || [...reason.trim()].length > 500}
      >
        核对更改
      </Button>
      <Button type="button" variant="quiet" onClick={close}>
        取消
      </Button>
      <ConfirmDialog
        open={!!pending}
        title="确认调整练习策略"
        description={
          version ? '该固定版本将对符合条件的学生开放。' : '学生将无法继续通过练习链接查看本题。'
        }
        confirmLabel="确认调整"
        busy={mutation.isPending}
        onCancel={() => setPending(null)}
        onConfirm={() => pending && mutation.mutate(pending)}
      >
        <p>{pending?.reason}</p>
      </ConfirmDialog>
    </form>
  )
}

export function PublicPracticePage() {
  const { id = '' } = useParams()
  const q = useQuery({
    queryKey: ['practiceProblem', id],
    queryFn: () => api.practiceProblem(id),
    gcTime: 0,
    staleTime: 0,
    refetchOnMount: 'always',
  })
  if (q.isPending || q.isFetching)
    return <StatePanel kind="loading" title="正在核对练习访问权限…" />
  if (q.isError)
    return (
      <StatePanel
        kind="error"
        title="练习当前不可用"
        description={q.error.message}
        onRetry={() => void q.refetch()}
      />
    )
  const p = q.data
  return (
    <article>
      <h1>{p.title}</h1>
      <p>公开练习题面 · 只读</p>
      <SafeMarkdown>{p.statement}</SafeMarkdown>
      <h2>公开样例</h2>
      {p.samples.map((s, i) => (
        <section key={i}>
          <h3>样例 {i + 1}</h3>
          <p>输入</p>
          <pre>{s.input}</pre>
          <p>输出</p>
          <pre>{s.output}</pre>
        </section>
      ))}
      <h2>运行环境</h2>
      {p.profile.languages.map((l) => (
        <p key={l.language_key}>
          {l.language_key} · {l.version} · CPU {l.cpu_time_ms} ms
        </p>
      ))}
    </article>
  )
}
