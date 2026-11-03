import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'
import { TextArea } from '../../components/ui/TextArea'

export function ControlsPage() {
  const config = useQuery({ queryKey: ['runtime-control'], queryFn: api.runtimeControl })
  const [reason, setReason] = useState(''),
    [incidentId, setIncidentId] = useState(''),
    [courseId, setCourseId] = useState(''),
    [grantId, setGrantId] = useState(''),
    [submissionId, setSubmissionId] = useState(''),
    [code, setCode] = useState('')
  const action = useMutation({
    mutationFn: async (command: string) => {
      if (command === 'submission' || command === 'judge') {
        const old = config.data!
        await api.updateRuntimeControl({
          submission_enabled:
            command === 'submission' ? !old.submission_enabled : old.submission_enabled,
          judge_enabled: command === 'judge' ? !old.judge_enabled : old.judge_enabled,
          expected_revision: old.revision,
          reason,
        })
        await config.refetch()
      }
      if (command === 'grant')
        setGrantId(
          (
            await api.grantEmergency({
              incident_id: incidentId,
              scope: { course_id: courseId },
              expires_at: new Date(Date.now() + 30 * 60000).toISOString(),
              reason,
            })
          ).grant_id,
        )
      if (command === 'revoke') {
        await api.revokeEmergency(grantId, { reason })
        setCode('')
      }
      if (command === 'read') setCode((await api.emergencySubmission(grantId, submissionId)).code)
    },
  })
  return (
    <>
      <h1>运行控制与应急访问</h1>
      <TextArea
        label="控制操作理由"
        hint="切换运行开关、申请或撤销授权前，请先填写操作理由。"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        maxLength={500}
      />
      <section className="panel stack">
        <h2>运行开关</h2>
        {!reason.trim() && <p className="field-hint">请先填写上方操作理由，填写后即可切换。</p>}
        {config.data && (
          <>
            <p>
              新提交 {config.data.submission_enabled ? '开启' : '暂停'} · 新评测派发{' '}
              {config.data.judge_enabled ? '开启' : '暂停'}
            </p>
            <Button
              disabled={!reason.trim()}
              busy={action.isPending}
              title={
                reason.trim()
                  ? '切换是否受理新的学生提交，已有任务继续处理。'
                  : '请先填写上方控制操作理由。'
              }
              onClick={() => action.mutate('submission')}
            >
              切换新提交受理
            </Button>
            <Button
              disabled={!reason.trim()}
              busy={action.isPending}
              title={
                reason.trim()
                  ? '切换新评测派发，已执行任务继续完成与清理。'
                  : '请先填写上方控制操作理由。'
              }
              onClick={() => action.mutate('judge')}
            >
              切换新评测派发
            </Button>
            <p>已执行任务继续完成与清理。</p>
          </>
        )}
        {config.error && <p role="alert">{config.error.message}</p>}
      </section>
      <section className="panel stack">
        <h2>限时应急授权</h2>
        <p className="field-hint">
          申请需填写操作理由、故障事件编号和该事件影响的课程编号；读取需填写授权编号和提交编号；撤销需填写授权编号及操作理由。
        </p>
        <Field
          label="关联故障事件编号"
          hint="从平台管理的故障事件列表复制实际事件编号。"
          value={incidentId}
          onChange={(e) => setIncidentId(e.target.value)}
        />
        <Field
          label="事件影响课程编号"
          hint="填写该事件所影响课程的实际编号，可从课程页面地址获取。"
          value={courseId}
          onChange={(e) => setCourseId(e.target.value)}
        />
        <Button
          disabled={!reason.trim() || !incidentId || !courseId}
          busy={action.isPending}
          title={
            !reason.trim() || !incidentId || !courseId
              ? '请填写操作理由、故障事件编号和事件影响课程编号。'
              : '申请本人30分钟应急读取权限，每次读取均记录审计。'
          }
          onClick={() => action.mutate('grant')}
        >
          申请本人30分钟课程授权
        </Button>
        <Field
          label="应急授权编号"
          hint="申请成功后自动填入，也可填写本人已有且有效的授权编号。"
          value={grantId}
          onChange={(e) => {
            setGrantId(e.target.value)
            setCode('')
          }}
        />
        <Field
          label="需读取的提交编号"
          hint="从本次授权课程的提交记录复制实际编号。"
          value={submissionId}
          onChange={(e) => {
            setSubmissionId(e.target.value)
            setCode('')
          }}
        />
        <Button
          disabled={!grantId || !submissionId}
          busy={action.isPending}
          title={
            !grantId || !submissionId
              ? '请填写本人有效授权编号和目标提交编号。'
              : '核对授权范围并读取提交源码，同时记录审计。'
          }
          onClick={() => action.mutate('read')}
        >
          审计并读取授权提交
        </Button>
        <Button
          disabled={!grantId || !reason.trim()}
          busy={action.isPending}
          title={
            !grantId || !reason.trim()
              ? '请填写本人授权编号和操作理由。'
              : '立即撤销本人这份应急授权。'
          }
          onClick={() => action.mutate('revoke')}
        >
          撤销本人授权
        </Button>
        {code && <TextArea label="应急授权源码" value={code} readOnly rows={12} />}
      </section>
      {action.error && <p role="alert">{action.error.message}</p>}
    </>
  )
}
