import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError } from '../../lib/api/client'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'
import { TextArea } from '../../components/ui/TextArea'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { teaching, type Preflight } from '../integrations/teaching'
import type { components } from '../../lib/api/schema'

type Version = components['schemas']['ProblemVersion']
export function VersionMaterials({
  version,
  revision,
  onRevision,
  reload,
  unsaved,
}: {
  version: Version
  revision: number
  onRevision: (r: number) => void
  reload: () => Promise<unknown>
  unsaved: boolean
}) {
  const id = version.version_id
  const [search, setSearch] = useSearchParams()
  const readOnly = !!version.published_at
  const [order, setOrder] = useState(1)
  const [input, setInput] = useState('')
  const [answer, setAnswer] = useState('')
  const [language, setLanguage] = useState<'cpp17' | 'python3'>(
    version.profile.languages[0].language_key,
  )
  const [code, setCode] = useState('')
  const [caseDirty, setCaseDirty] = useState(false)
  const [referenceDirty, setReferenceDirty] = useState(false)
  const [job, setJob] = useState<{ revision: number; result: Preflight } | null>(null)
  const [reason, setReason] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [deleteOrder, setDeleteOrder] = useState<number | null>(null)
  const [reloadError, setReloadError] = useState('')
  const cache = useQueryClient()
  const cases = useQuery({ queryKey: ['testcases', id], queryFn: () => api.testcases(id) })
  const refs = useQuery({ queryKey: ['references', id], queryFn: () => api.references(id) })
  function refreshed(next: number) {
    onRevision(next)
    void cache.invalidateQueries({ queryKey: ['testcases', id] })
    void cache.invalidateQueries({ queryKey: ['references', id] })
    void reload()
  }
  const saveCase = useMutation({
    mutationFn: () =>
      api.putTestcase(id, order, {
        input_text: input,
        answer_text: answer,
        expected_revision: revision,
      }),
    onSuccess: (v) => {
      refreshed(v.revision)
      setCaseDirty(false)
    },
  })
  const removeCase = useMutation({
    mutationFn: () => api.deleteTestcase(id, deleteOrder!, { expected_revision: revision }),
    onSuccess: () => {
      refreshed(revision + 1)
      setDeleteOrder(null)
    },
  })
  const saveReference = useMutation({
    mutationFn: () => api.putReference(id, language, { code, expected_revision: revision }),
    onSuccess: (v) => {
      refreshed(v.revision)
      setReferenceDirty(false)
    },
  })
  const start = useMutation({
    mutationFn: (r: number) => teaching.preflight.enqueue(id, r),
  })
  const pointer = search.get('preflight') || ''
  const pointerRevision = Number(search.get('preflightRevision'))
  const activeId =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(pointer) &&
    Number.isSafeInteger(pointerRevision) &&
    pointerRevision > 0 &&
    pointerRevision === revision
      ? pointer.toLowerCase()
      : null
  const activeJob =
    job?.revision === revision && job.result.preflight_id === activeId ? job.result : null
  const progress = useQuery({
    queryKey: ['preflight', id, activeId, revision],
    queryFn: async () => {
      const value = await teaching.preflight.read(activeId!)
      if (value.version_id !== id || value.preflight_id !== activeId)
        throw new ApiError(
          409,
          'PREFLIGHT_VERSION_MISMATCH',
          '预检记录与当前版本不匹配，请重新预检。',
        )
      if (value.current_revision !== revision || !value.matches_current)
        throw new ApiError(
          409,
          'PREFLIGHT_CONTENT_MISMATCH',
          '草稿内容已变更，请重新读取修订或启动预检。',
        )
      return value
    },
    enabled: !!activeId,
    refetchInterval: (query) =>
      query.state.error || ['PASSED', 'FAILED'].includes(query.state.data?.state || '')
        ? false
        : 2000,
  })
  const checkedProgress =
    !progress.isError &&
    progress.data?.current_revision === revision &&
    progress.data.matches_current
      ? progress.data
      : undefined
  const result = progress.isError ? undefined : checkedProgress || activeJob
  const publish = useMutation({
    mutationFn: () =>
      api.publishVersion(id, {
        expected_revision: revision,
        preflight_id: activeId!,
        reason,
      }),
    onSuccess: () => {
      setConfirm(false)
      void reload()
    },
  })
  const dirty = unsaved || caseDirty || referenceDirty
  const error =
    saveCase.error ||
    saveReference.error ||
    removeCase.error ||
    start.error ||
    progress.error ||
    publish.error
  const pending =
    saveCase.isPending || saveReference.isPending || removeCase.isPending || publish.isPending
  return (
    <>
      <fieldset className="material-fields" disabled={pending}>
        <section className="management-panel">
          <h2>配对测试</h2>
          <p>隐藏数据仅用于教师维护和预检，不会进入学生题面。</p>
          {cases.error && <p role="alert">{cases.error.message}</p>}
          <div className="action-row">
            {cases.data?.items.map((c) => (
              <span key={c.testcase_id}>
                <Button
                  variant="secondary"
                  disabled={caseDirty}
                  onClick={() => {
                    setOrder(c.order)
                    setInput(c.input_text)
                    setAnswer(c.answer_text)
                    setCaseDirty(false)
                  }}
                >
                  载入测试 {c.order}
                </Button>
                {!readOnly && (
                  <Button variant="quiet" onClick={() => setDeleteOrder(c.order)}>
                    删除测试 {c.order}
                  </Button>
                )}
              </span>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              saveCase.mutate()
            }}
          >
            <Field
              label="测试编号"
              type="number"
              value={order}
              min={1}
              max={10}
              required
              readOnly={readOnly}
              onChange={(e) => {
                setOrder(Number(e.target.value))
                setCaseDirty(true)
              }}
            />
            <div className="pair-fields">
              <TextArea
                label="测试输入"
                value={input}
                rows={4}
                readOnly={readOnly}
                onChange={(e) => {
                  setInput(e.target.value)
                  setCaseDirty(true)
                }}
              />
              <TextArea
                label="预期答案"
                value={answer}
                rows={4}
                readOnly={readOnly}
                onChange={(e) => {
                  setAnswer(e.target.value)
                  setCaseDirty(true)
                }}
              />
            </div>
            {!readOnly && (
              <Button type="submit" busy={saveCase.isPending}>
                保存配对测试
              </Button>
            )}
            {saveCase.isSuccess && <p role="status">测试点已保存。</p>}
          </form>
        </section>
        <section className="management-panel">
          <h2>参考程序</h2>
          <p>每种允许语言各保存一份参考程序。</p>
          {refs.error && <p role="alert">{refs.error.message}</p>}
          <form
            onSubmit={(e) => {
              e.preventDefault()
              saveReference.mutate()
            }}
          >
            <label className="field">
              参考语言
              <select
                value={language}
                disabled={referenceDirty}
                onChange={(e) => {
                  const lang = e.target.value as 'cpp17' | 'python3'
                  setLanguage(lang)
                  setCode(refs.data?.items.find((r) => r.language_key === lang)?.code || '')
                  setReferenceDirty(false)
                }}
              >
                {version.profile.languages.map((l) => (
                  <option key={l.language_key} value={l.language_key}>
                    {l.language_key}
                  </option>
                ))}
              </select>
            </label>
            <Button
              variant="quiet"
              disabled={referenceDirty || refs.isPending || !!refs.error}
              onClick={() => {
                setCode(refs.data?.items.find((r) => r.language_key === language)?.code || '')
                setReferenceDirty(false)
              }}
            >
              载入已保存参考程序
            </Button>
            <TextArea
              label="参考程序"
              value={code}
              rows={8}
              required
              readOnly={readOnly}
              onChange={(e) => {
                setCode(e.target.value)
                setReferenceDirty(true)
              }}
            />
            {!readOnly && (
              <Button type="submit" busy={saveReference.isPending}>
                保存参考程序
              </Button>
            )}
            {saveReference.isSuccess && <p role="status">参考程序已保存。</p>}
          </form>
        </section>
        {!readOnly && (
          <section className="management-panel">
            <h2>预检与发布</h2>
            <p>预检必须通过全部语言、公开样例和隐藏测试。修改内容后需要重新预检。</p>
            <Button
              onClick={() =>
                start.mutate(revision, {
                  onSuccess: (value, r) => {
                    setJob({ result: value, revision: r })
                    const next = new URLSearchParams(search)
                    next.set('preflight', value.preflight_id)
                    next.set('preflightRevision', String(r))
                    setSearch(next, { replace: true })
                  },
                })
              }
              busy={start.isPending}
              disabled={dirty}
            >
              启动预检
            </Button>
            {dirty && <p>请先保存所有修改。</p>}
            {activeId && (
              <p role="status">
                预检状态：{result?.state || (progress.isError ? '不可用' : '正在读取')}
                {checkedProgress?.summary ? ` · ${checkedProgress.summary}` : ''}
              </p>
            )}
            {checkedProgress && (
              <ul aria-label="预检测试进度">
                {checkedProgress.cases.map((item) => (
                  <li key={`${item.language_key}:${item.case_kind}:${item.case_order}`}>
                    {item.language_key} · {item.case_kind === 'SAMPLE' ? '样例' : '隐藏测试'}{' '}
                    {item.case_order}：{item.verdict || item.state}
                  </li>
                ))}
              </ul>
            )}
            <Field
              label="发布理由"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              minLength={10}
              maxLength={500}
              hint="10—500 个字符。发布后该版本内容不可修改。"
            />
            <Button
              variant="secondary"
              onClick={() => setConfirm(true)}
              disabled={
                dirty ||
                !activeId ||
                progress.isError ||
                checkedProgress?.state !== 'PASSED' ||
                [...reason].length < 10
              }
            >
              发布题目版本
            </Button>
          </section>
        )}
        {error && (
          <div role="alert" className="form-error">
            <p>{error.message}</p>
            <Button
              variant="quiet"
              onClick={async () => {
                try {
                  await reload()
                  saveCase.reset()
                  saveReference.reset()
                  removeCase.reset()
                  publish.reset()
                  start.reset()
                  if (activeId) void progress.refetch()
                  setReloadError('')
                } catch (e) {
                  setReloadError((e as Error).message)
                }
              }}
            >
              重新读取修订，保留测试和参考程序输入
            </Button>
          </div>
        )}
        {reloadError && <p role="alert">{reloadError}</p>}
      </fieldset>
      <ConfirmDialog
        open={confirm}
        title="确认发布题目版本"
        description={`发布「${version.title}」修订 ${revision}。该版本将固定题面、测试、参考程序和运行环境。`}
        confirmLabel="确认发布"
        onCancel={() => setConfirm(false)}
        onConfirm={() => publish.mutate()}
        busy={publish.isPending}
      />
      <ConfirmDialog
        open={deleteOrder !== null}
        title="确认删除测试点"
        description={`删除测试 ${deleteOrder} 后，发布前需要保持测试编号连续。`}
        confirmLabel="确认删除"
        onCancel={() => setDeleteOrder(null)}
        onConfirm={() => removeCase.mutate()}
        busy={removeCase.isPending}
      />
    </>
  )
}
