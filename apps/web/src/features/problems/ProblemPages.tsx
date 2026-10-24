import { useInfiniteQuery, useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useState, type FormEvent } from 'react'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'
import { TextArea } from '../../components/ui/TextArea'
import { StatePanel } from '../../components/ui/StatePanel'
import { SafeMarkdown } from '../../components/ui/SafeMarkdown'
import type { components } from '../../lib/api/schema'
import { VersionMaterials } from './VersionMaterials'

type Schema = components['schemas']
type Content = Pick<
  Schema['CreateVersion'],
  'title' | 'statement' | 'samples' | 'tags' | 'profile' | 'source_ref'
>
export function ProblemsPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const list = useInfiniteQuery({
    queryKey: ['problems', id],
    queryFn: ({ pageParam }) => api.problems(id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
  })
  const create = useMutation({
    mutationFn: () => api.createProblem({ course_id: id }),
    onSuccess: (result) => navigate(`/teacher/problems/${result.problem_id}/new`),
  })
  return (
    <>
      <Link to={`/courses/${id}`} className="back-link">
        ← 返回课程
      </Link>
      <header className="page-heading">
        <div>
          <h1>课程题库</h1>
          <p>维护题目、测试和不可变的发布版本。</p>
        </div>
        <Button onClick={() => create.mutate()} busy={create.isPending}>
          新建题目
        </Button>
      </header>
      {create.error && (
        <p role="alert" className="form-error">
          {create.error.message}
        </p>
      )}
      {list.isPending ? (
        <StatePanel kind="loading" title="正在读取题库…" />
      ) : list.isError ? (
        <StatePanel
          kind="error"
          title="题库不可用"
          description={list.error.message}
          onRetry={() => void list.refetch()}
        />
      ) : (
        <ul className="resource-list">
          {list.data.pages
            .flatMap((p) => p.items)
            .map((p) => (
              <li key={p.problem_id}>
                <Link to={`/teacher/problems/${p.problem_id}`}>{p.title}</Link>
                <span>{p.status === 'PUBLISHED' ? '已有发布版本' : '草稿'}</span>
              </li>
            ))}
          {!list.data.pages.some((p) => p.items.length) && <li>还没有题目。</li>}
        </ul>
      )}
      {list.hasNextPage && (
        <Button onClick={() => void list.fetchNextPage()} busy={list.isFetchingNextPage}>
          加载更多题目
        </Button>
      )}
    </>
  )
}
export function VersionsPage() {
  const { id = '' } = useParams()
  const list = useInfiniteQuery({
    queryKey: ['versions', id],
    queryFn: ({ pageParam }) => api.versions(id, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
  })
  return (
    <>
      <header className="page-heading">
        <h1>题目版本</h1>
        <Link className="button button--secondary" to={`/teacher/problems/${id}/new`}>
          新建版本
        </Link>
      </header>
      {list.isPending ? (
        <StatePanel kind="loading" title="正在读取版本…" />
      ) : list.isError ? (
        <StatePanel
          kind="error"
          title="版本不可用"
          description={list.error.message}
          onRetry={() => void list.refetch()}
        />
      ) : (
        <ul className="resource-list">
          {list.data.pages
            .flatMap((p) => p.items)
            .map((v) => (
              <li key={v.version_id}>
                <Link to={`/teacher/problem-versions/${v.version_id}`}>{v.title}</Link>
                <span>
                  {v.published_at ? '已发布 · 只读' : '草稿'} · 修订 {v.revision}
                </span>
                <Link to={`/teacher/problems/${id}/new?base=${v.version_id}`}>复制为新版本</Link>
              </li>
            ))}
        </ul>
      )}
      {list.hasNextPage && <Button onClick={() => void list.fetchNextPage()}>加载更多版本</Button>}
    </>
  )
}
export function CreateVersionPage() {
  const { id = '' } = useParams()
  const [search] = useSearchParams()
  const base = search.get('base')
  const profiles = useQuery({ queryKey: ['profiles'], queryFn: api.profiles })
  const original = useQuery({
    queryKey: ['version', base],
    queryFn: () => api.version(base!),
    enabled: !!base,
  })
  const navigate = useNavigate()
  const create = useMutation({
    mutationFn: (content: Content) =>
      api.createVersion({ ...content, problem_id: id, ...(base ? { base_version_id: base } : {}) }),
    onSuccess: (v) =>
      navigate(`/teacher/problem-versions/${v.version_id}`, {
        replace: true,
        state: { saved: true },
      }),
  })
  if (profiles.isPending || (base && original.isPending))
    return <StatePanel kind="loading" title="正在读取运行环境…" />
  if (profiles.isError || original.isError)
    return (
      <StatePanel
        kind="error"
        title="无法准备题目草稿"
        description={(profiles.error || original.error)?.message}
        onRetry={() => {
          void profiles.refetch()
          if (base) void original.refetch()
        }}
      />
    )
  if (!profiles.data.items.length)
    return (
      <StatePanel
        kind="empty"
        title="尚未配置运行环境"
        description="请联系管理员提供已验证的语言环境。"
      />
    )
  return (
    <>
      <Link to={`/teacher/problems/${id}`} className="back-link">
        ← 题目版本
      </Link>
      <h1>{base ? '复制新版本' : '新建题目草稿'}</h1>
      <ProblemForm
        initial={
          original.data || {
            title: '',
            statement: '',
            samples: [{ input: '', output: '' }],
            tags: [],
            profile: profiles.data.items[0],
            source_ref: '',
          }
        }
        profiles={profiles.data.items}
        onSave={(c) => create.mutate(c)}
        busy={create.isPending}
        error={create.error?.message}
      />
    </>
  )
}
export function VersionPage() {
  const { id = '' } = useParams()
  const query = useQuery({ queryKey: ['version', id], queryFn: () => api.version(id) })
  if (query.isPending) return <StatePanel kind="loading" title="正在读取题目…" />
  if (query.isError)
    return (
      <StatePanel
        kind="error"
        title="题目不可用"
        description={query.error.message}
        onRetry={() => void query.refetch()}
      />
    )
  return <VersionWorkspace key={id} version={query.data} reload={() => query.refetch()} />
}
function VersionWorkspace({
  version,
  reload,
}: {
  version: Schema['ProblemVersion']
  reload: () => Promise<unknown>
}) {
  const [revision, setRevision] = useState(version.revision)
  const [saved, setSaved] = useState(true)
  const [reloadError, setReloadError] = useState('')
  const mutation = useMutation({
    mutationFn: (content: Content) =>
      api.updateVersion(version.version_id, { ...content, expected_revision: revision }),
    onSuccess: (result) => {
      setRevision(result.revision)
      setSaved(true)
      void reload()
    },
  })
  return (
    <>
      <Link to={`/teacher/problems/${version.problem_id}`} className="back-link">
        ← 题目版本
      </Link>
      <header className="page-heading">
        <div>
          <h1>{version.title}</h1>
          <p>
            {version.published_at ? '已发布版本 · 内容只读' : '草稿'} · 修订 {revision}
          </p>
        </div>
        <Link to={`/teacher/problems/${version.problem_id}/new?base=${version.version_id}`}>
          复制为新版本
        </Link>
      </header>
      <ProblemForm
        initial={version}
        profiles={[version.profile]}
        onSave={(c) => mutation.mutate(c)}
        onEdit={() => setSaved(false)}
        busy={mutation.isPending}
        error={mutation.error?.message}
        readOnly={!!version.published_at}
      />
      {saved && <p role="status">题面已保存。</p>}
      {mutation.error && (
        <Button
          variant="secondary"
          onClick={async () => {
            try {
              const latest = await api.version(version.version_id)
              setRevision(latest.revision)
              await reload()
              mutation.reset()
            } catch (e) {
              setReloadError((e as Error).message)
            }
          }}
        >
          重新读取版本，保留输入
        </Button>
      )}
      {reloadError && <p role="alert">{reloadError}</p>}
      <VersionMaterials
        version={version}
        revision={revision}
        onRevision={setRevision}
        reload={reload}
        unsaved={!saved}
      />
    </>
  )
}
function ProblemForm({
  initial,
  profiles,
  onSave,
  onEdit,
  busy,
  error,
  readOnly = false,
}: {
  initial: Content
  profiles: Schema['Profile'][]
  onSave: (c: Content) => void
  onEdit?: () => void
  busy: boolean
  error?: string
  readOnly?: boolean
}) {
  const [value, setValue] = useState(initial)
  const [preview, setPreview] = useState(false)
  function update<K extends keyof Content>(key: K, next: Content[K]) {
    setValue((v) => ({ ...v, [key]: next }))
    onEdit?.()
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    onSave(value)
  }
  return (
    <form className="management-panel" onSubmit={submit}>
      <Field
        label="题目标题"
        value={value.title}
        onChange={(e) => update('title', e.target.value)}
        required
        maxLength={100}
        readOnly={readOnly}
      />
      <TextArea
        label="题目说明"
        value={value.statement}
        onChange={(e) => update('statement', e.target.value)}
        rows={8}
        required
        readOnly={readOnly}
        hint="支持 Markdown；不显示原始 HTML 或外链图片。UTF-8 上限 32 KiB。"
      />
      <Button variant="quiet" type="button" onClick={() => setPreview(!preview)}>
        {preview ? '关闭预览' : '预览题面'}
      </Button>
      {preview && <SafeMarkdown>{value.statement}</SafeMarkdown>}
      {value.samples.map((s, i) => (
        <div className="pair-fields" key={i}>
          <TextArea
            label={`样例 ${i + 1} 输入`}
            value={s.input}
            rows={3}
            readOnly={readOnly}
            onChange={(e) =>
              update(
                'samples',
                value.samples.map((x, j) => (j === i ? { ...x, input: e.target.value } : x)),
              )
            }
          />
          <TextArea
            label={`样例 ${i + 1} 输出`}
            value={s.output}
            rows={3}
            readOnly={readOnly}
            onChange={(e) =>
              update(
                'samples',
                value.samples.map((x, j) => (j === i ? { ...x, output: e.target.value } : x)),
              )
            }
          />
          {!readOnly && value.samples.length > 1 && (
            <Button
              variant="quiet"
              onClick={() =>
                update(
                  'samples',
                  value.samples.filter((_, j) => i !== j),
                )
              }
            >
              删除样例 {i + 1}
            </Button>
          )}
        </div>
      ))}
      {!readOnly && value.samples.length < 3 && (
        <Button
          variant="secondary"
          onClick={() => update('samples', [...value.samples, { input: '', output: '' }])}
        >
          添加样例
        </Button>
      )}
      <Field
        label="知识点标签"
        hint="以英文逗号分隔，最多5项，每项20字符。"
        value={value.tags.join(',')}
        onChange={(e) => update('tags', e.target.value ? e.target.value.split(',') : [])}
        readOnly={readOnly}
      />
      <label className="field">
        运行环境
        <select
          value={value.profile.profile_id}
          disabled={readOnly}
          onChange={(e) =>
            update(
              'profile',
              profiles.find((p) => p.profile_id === e.target.value)!,
            )
          }
        >
          {profiles.map((p) => (
            <option key={p.profile_id} value={p.profile_id}>
              {p.languages.map((l) => `${l.language_key} · ${l.version}`).join(' / ')}
            </option>
          ))}
        </select>
      </label>
      <Field
        label="来源说明"
        value={value.source_ref}
        onChange={(e) => update('source_ref', e.target.value)}
        maxLength={500}
        readOnly={readOnly}
      />
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {!readOnly && (
        <Button type="submit" busy={busy}>
          保存题面
        </Button>
      )}
    </form>
  )
}
