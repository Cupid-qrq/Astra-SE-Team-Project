import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { Field } from '../../components/ui/Field'
import { TextArea } from '../../components/ui/TextArea'
import type { components } from '../../lib/api/schema'
import { inspectTemplate, names, readSnapshot, storeSnapshot, type Fields } from './templateDraft'

type Draft = components['schemas']['TemplateDraftView']
type Command = components['schemas']['PublishCommand']
export function TemplateEditor({
  initial,
  ownerId,
  courseId,
  onCreated,
  onReload,
}: {
  initial?: Draft
  ownerId: string
  courseId?: string
  onCreated?: (id: string) => void
  onReload?: () => void
}) {
  const cache = useQueryClient()
  const id = initial?.template_id
  const key = `astra:hint-template:${ownerId}:${id || 'new:' + (courseId || 'GLOBAL')}`
  const [saved, setSaved] = useState<Fields>(() => ({
    body: initial?.body ?? '',
    schema_version: initial?.schema_version ?? '1',
    allowed_placeholders: initial?.allowed_placeholders ?? [],
  }))
  const [fields, setFields] = useState(saved)
  const [revision, setRevision] = useState(initial?.revision ?? 1)
  const [published, setPublished] = useState(initial?.published_version_no ?? null)
  const [recovery, setRecovery] = useState(() => readSnapshot(key))
  const [storageFailed, setStorageFailed] = useState(false)
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState<Command | null>(null)
  const [notice, setNotice] = useState('')
  const archived = initial?.course_status === 'ARCHIVED'
  const dirty = JSON.stringify(fields) !== JSON.stringify(saved)
  const { error, preview, bytes } = inspectTemplate(fields)
  const save = useMutation({
    mutationFn: async () => {
      if (id) return api.saveTemplate(id, { ...fields, expected_revision: revision })
      return api.createTemplate({
        scope: courseId ? 'COURSE' : 'GLOBAL',
        ...(courseId ? { course_id: courseId } : {}),
        draft: fields,
      })
    },
    onSuccess: (value) => {
      storeSnapshot(key, null)
      void cache.invalidateQueries({ queryKey: ['templates'] })
      if ('template_id' in value && typeof value.template_id === 'string') {
        onCreated?.(value.template_id)
        return
      }
      setSaved(fields)
      setRevision(value.revision)
      setNotice('草稿已保存。')
      cache.setQueryData<Draft>(['templateDraft', id], (current) => ({
        ...(current ?? initial!),
        ...fields,
        revision: value.revision,
      }))
    },
  })
  const publish = useMutation({
    mutationFn: (command: Command) => api.publishTemplate(id!, command),
    onSuccess: (result, command) => {
      const next = (published ?? 0) + 1
      setPublished(next)
      setRevision(command.expected_revision + 1)
      setReason('')
      setNotice('新版本已发布。')
      cache.setQueryData(['templateDraft', id], {
        ...initial,
        ...saved,
        revision: command.expected_revision + 1,
        published_version_id: result.version_id,
        published_version_no: next,
      })
      void cache.invalidateQueries({ queryKey: ['templates'] })
      void cache.invalidateQueries({ queryKey: ['templateHistory', id] })
    },
    onSettled: () => setPending(null),
  })
  const busy = save.isPending || publish.isPending || !!pending
  function edit(next: Fields) {
    setFields(next)
    setRecovery(null)
    setNotice('')
    setStorageFailed(
      !storeSnapshot(
        key,
        JSON.stringify(next) === JSON.stringify(saved) ? null : { fields: next, revision },
      ),
    )
  }
  return (
    <>
      {id && (
        <p className="notice">
          草稿版本 {revision} · {published ? `最新发布版本 ${published}` : '尚未发布'}
          。发布后还需管理员启用，才会用于新的 AI 提示。
        </p>
      )}
      {archived && <p className="notice">课程已归档，此模板只读。</p>}
      {recovery && (
        <div className="notice">
          <p>本账号有未保存的模板内容。</p>
          <Button
            variant="secondary"
            disabled={archived || busy}
            onClick={() => {
              setFields(recovery.fields)
              setRevision(recovery.revision)
              setRecovery(null)
            }}
          >
            恢复本地编辑
          </Button>
          <Button
            variant="quiet"
            disabled={busy}
            onClick={() => {
              storeSnapshot(key, null)
              setRecovery(null)
            }}
          >
            放弃本地恢复
          </Button>
        </div>
      )}
      <div className="feedback-layout template-layout">
        <form
          className="panel stack"
          onSubmit={(e) => {
            e.preventDefault()
            if (!error && !busy && !archived && (dirty || !id)) save.mutate()
          }}
        >
          <h2>{id ? '编辑草稿' : '新建草稿'}</h2>
          <fieldset className="material-fields stack" disabled={busy || archived}>
            <TextArea
              label="给 AI 的指导要求"
              rows={8}
              maxLength={8192}
              value={fields.body}
              hint="勾选下方信息后，用花括号写入要求中，例如 {question} 会自动替换成学生的问题。"
              onChange={(e) => edit({ ...fields, body: e.target.value })}
            />
            <fieldset className="material-fields template-placeholders">
              <legend>自动填入的信息</legend>
              {names.map((name) => (
                <label key={name} className="button-row">
                  <input
                    type="checkbox"
                    checked={fields.allowed_placeholders.includes(name)}
                    onChange={(e) =>
                      edit({
                        ...fields,
                        allowed_placeholders: e.target.checked
                          ? [...fields.allowed_placeholders, name]
                          : fields.allowed_placeholders.filter((n) => n !== name),
                      })
                    }
                  />
                  {{
                    verdict: '评测结果',
                    question: '学生的问题',
                    student_code: '学生代码',
                    public_problem: '公开题面',
                    public_samples: '公开样例',
                    sanitized_diagnostic: '已脱敏的错误信息',
                  }[name] ?? name}{' '}
                  <span className="muted">{'{' + name + '}'}</span>
                </label>
              ))}
            </fieldset>
            <Field
              label="回复格式版本"
              maxLength={40}
              value={fields.schema_version}
              onChange={(e) => edit({ ...fields, schema_version: e.target.value })}
            />
          </fieldset>
          <p className="muted">{bytes} / 8192 字节</p>
          {error && <p className="field-error">{error}</p>}
          {storageFailed && <p role="alert">浏览器无法保留草稿，请在离开前复制正文。</p>}
          <Button
            type="submit"
            busy={save.isPending}
            disabled={archived || busy || !!error || (!!id && !dirty)}
          >
            {id ? '保存草稿' : '创建草稿'}
          </Button>
          {id && (
            <>
              <TextArea
                label="发布理由"
                value={reason}
                maxLength={500}
                disabled={archived || busy}
                hint="10—500 字，发布后保留这次内容，之后修改需要发布新版本。"
                onChange={(e) => setReason(e.target.value)}
              />
              <Button
                disabled={archived || dirty || busy || !!error || [...reason.trim()].length < 10}
                onClick={() => setPending({ expected_revision: revision, reason: reason.trim() })}
              >
                发布新版本
              </Button>
            </>
          )}
          {(save.error || publish.error) && (
            <div role="alert">
              <p>{(save.error || publish.error)?.message} 当前编辑已保留。</p>
              {id && (
                <Button variant="secondary" onClick={onReload}>
                  重新载入服务器草稿（保留本地恢复）
                </Button>
              )}
            </div>
          )}
          {notice && <p role="status">{notice}</p>}
        </form>
        <section className="panel stack" aria-label="示例预览">
          <h2>示例预览</h2>
          <p className="muted">用一组教学样例预览 AI 实际收到的要求。</p>
          <pre className="template-text">{preview}</pre>
        </section>
      </div>
      <ConfirmDialog
        open={!!pending}
        title="发布AI 辅导设置新版本"
        description={`将发布已保存的草稿版本 ${pending?.expected_revision ?? ''}。历史版本可继续查阅。`}
        confirmLabel="确认发布"
        busy={publish.isPending}
        onCancel={() => setPending(null)}
        onConfirm={() => {
          if (pending) publish.mutate(pending)
        }}
      >
        <p>{pending?.reason}</p>
      </ConfirmDialog>
    </>
  )
}
