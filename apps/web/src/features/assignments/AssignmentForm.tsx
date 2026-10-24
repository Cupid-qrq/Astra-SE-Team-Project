import { useMutation, useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../app/runtime'
import type { components } from '../../lib/api/schema'
import { Field } from '../../components/ui/Field'
import { Button } from '../../components/ui/Button'
import { StatePanel } from '../../components/ui/StatePanel'

type Schema = components['schemas']
import { beijingInput, fromBeijing, beijingTime } from './time'

async function candidates(courseId: string) {
  const problems: Schema['Problem'][] = []
  let cursor: string | undefined
  do {
    const page = await api.problems(courseId, cursor)
    problems.push(...page.items)
    cursor = page.next_cursor || undefined
  } while (cursor)
  return Promise.all(
    problems.map(async (p) => {
      const versions: Schema['ProblemVersion'][] = []
      let next: string | undefined
      do {
        const page = await api.versions(p.problem_id, next)
        versions.push(...page.items.filter((v) => !!v.published_at))
        next = page.next_cursor || undefined
      } while (next)
      return {
        ...p,
        versions: versions.sort(
          (a, b) =>
            b.published_at!.localeCompare(a.published_at!) ||
            a.version_id.localeCompare(b.version_id),
        ),
      }
    }),
  )
}
export function AssignmentForm({
  courseId,
  existing,
  onSaved,
}: {
  courseId: string
  existing?: Schema['AssignmentView']
  onSaved?: () => void
}) {
  const query = useQuery({
    queryKey: ['assignment-options', courseId, existing?.assignment_id],
    queryFn: async () => {
      const [options, original] = await Promise.all([
        candidates(courseId),
        existing
          ? Promise.all(
              existing.items.map(async (item) => ({
                problem_id: item.problem_id,
                points: item.points,
                version_id: (await api.assignmentProblem(existing.assignment_id, item.problem_id))
                  .version_id,
              })),
            )
          : Promise.resolve([]),
      ])
      return { options: options.filter((p) => p.versions.length), original }
    },
  })
  if (query.isPending) return <StatePanel kind="loading" title="正在读取可用题目版本…" />
  if (query.isError)
    return (
      <StatePanel
        kind="error"
        title="无法准备作业"
        description={query.error.message}
        onRetry={() => void query.refetch()}
      />
    )
  return <FormFields courseId={courseId} existing={existing} onSaved={onSaved} {...query.data} />
}
function FormFields({
  courseId,
  existing,
  options,
  original,
  onSaved,
}: {
  courseId: string
  existing?: Schema['AssignmentView']
  options: Awaited<ReturnType<typeof candidates>>
  original: Schema['AssignmentItem'][]
  onSaved?: () => void
}) {
  const [title, setTitle] = useState(existing?.title || '')
  const [open, setOpen] = useState(existing ? beijingInput(existing.open_at) : '')
  const [due, setDue] = useState(existing ? beijingInput(existing.due_at) : '')
  const [policy, setPolicy] = useState<'DISABLED' | 'GUIDED'>(existing?.ai_policy || 'DISABLED')
  const [items, setItems] = useState(original)
  const [revision, setRevision] = useState(existing?.revision || 1)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const mutation = useMutation({
    mutationFn: async (body: Schema['CreateAssignment']) =>
      existing
        ? api.updateAssignment(existing.assignment_id, { ...body, expected_revision: revision })
        : api.createAssignment(body),
    onSuccess: (value) => {
      setRevision(value.revision)
      if ('assignment_id' in value)
        navigate(`/assignments/${value.assignment_id}`, { replace: true })
      onSaved?.()
    },
  })
  const total = items.reduce((sum, item) => sum + item.points, 0)
  function submit(event: FormEvent) {
    event.preventDefault()
    if (total !== 100 || !items.length || items.length > 20) {
      setError('请选择1—20道题，各题正整数分值合计100分。')
      return
    }
    if (!open || !due || fromBeijing(open) >= fromBeijing(due)) {
      setError('开放时间必须早于截止时间。')
      return
    }
    setError('')
    mutation.mutate({
      course_id: courseId,
      title,
      items,
      open_at: fromBeijing(open),
      due_at: fromBeijing(due),
      ai_policy: policy,
    })
  }
  return (
    <form className="management-panel" onSubmit={submit}>
      <Field
        label="作业标题"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        required
        maxLength={100}
      />
      <div className="pair-fields">
        <Field
          label="开放时间（北京时间）"
          type="datetime-local"
          value={open}
          onChange={(e) => setOpen(e.target.value)}
          required
        />
        <Field
          label="截止时间（北京时间）"
          type="datetime-local"
          value={due}
          onChange={(e) => setDue(e.target.value)}
          required
        />
      </div>
      <label className="field">
        提示策略
        <select value={policy} onChange={(e) => setPolicy(e.target.value as 'DISABLED' | 'GUIDED')}>
          <option value="DISABLED">关闭模型提示</option>
          <option value="GUIDED">允许引导提示</option>
        </select>
      </label>
      <h2>选择题目与分值</h2>
      <p>只可选择本课程已发布并通过预检的版本；发布后题目与分值固定。</p>
      {options.length === 0 && <p>暂无可用版本，请先完成题目预检与发布。</p>}
      {options.map((p) => {
        const selected = items.find((i) => i.problem_id === p.problem_id)
        return (
          <div className="assignment-choice" key={p.problem_id}>
            <label>
              <input
                type="checkbox"
                aria-label={`选择题目 ${p.title}`}
                checked={!!selected}
                onChange={(e) =>
                  setItems(
                    e.target.checked
                      ? [
                          ...items,
                          {
                            problem_id: p.problem_id,
                            version_id: p.versions[0].version_id,
                            points: 100,
                          },
                        ]
                      : items.filter((i) => i.problem_id !== p.problem_id),
                  )
                }
              />
              {p.title}
            </label>
            {selected && (
              <>
                <label className="field">
                  {p.title} 版本
                  <select
                    value={selected.version_id}
                    onChange={(e) =>
                      setItems(
                        items.map((i) =>
                          i.problem_id === p.problem_id ? { ...i, version_id: e.target.value } : i,
                        ),
                      )
                    }
                  >
                    {p.versions.map((v) => (
                      <option key={v.version_id} value={v.version_id}>
                        {beijingTime(v.published_at!)} · {v.version_id.slice(0, 8)}
                      </option>
                    ))}
                  </select>
                </label>
                <Field
                  label={`${p.title} 分值`}
                  type="number"
                  min={1}
                  max={100}
                  step={1}
                  required
                  value={selected.points}
                  onChange={(e) =>
                    setItems(
                      items.map((i) =>
                        i.problem_id === p.problem_id
                          ? { ...i, points: Number(e.target.value) }
                          : i,
                      ),
                    )
                  }
                />
              </>
            )}
          </div>
        )
      })}
      <p role="status">
        已选择 {items.length} 道题 · 总分 {total} / 100
      </p>
      {(error || mutation.error) && (
        <p role="alert" className="form-error">
          {error || mutation.error?.message}
        </p>
      )}
      {mutation.isSuccess && <p role="status">作业草稿已保存。</p>}
      <Button type="submit" busy={mutation.isPending}>
        保存作业草稿
      </Button>
      {mutation.error && existing && (
        <Button
          variant="quiet"
          onClick={async () => {
            try {
              setRevision((await api.assignment(existing.assignment_id)).revision)
              mutation.reset()
            } catch (e) {
              setError((e as Error).message)
            }
          }}
        >
          读取最新修订，保留输入
        </Button>
      )}
    </form>
  )
}
