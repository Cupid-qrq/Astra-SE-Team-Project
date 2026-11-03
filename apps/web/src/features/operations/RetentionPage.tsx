import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, sessionKey } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { Field } from '../../components/ui/Field'
import { TextArea } from '../../components/ui/TextArea'
import { beijingTime } from '../assignments/time'

export function RetentionPage() {
  const session = useQuery({ queryKey: sessionKey, queryFn: api.session })
  const [courseId, setCourseId] = useState(''),
    [planId, setPlanId] = useState(''),
    [confirmationId, setConfirmationId] = useState(''),
    [holdId, setHoldId] = useState(''),
    [reason, setReason] = useState('')
  const course = useQuery({
    queryKey: ['course', courseId],
    queryFn: () => api.course(courseId),
    enabled: !!courseId && session.data?.user?.role === 'TEACHER',
  })
  const plan = useQuery({
    queryKey: ['retention', planId],
    queryFn: () => api.retention(planId),
    enabled: !!planId,
  })
  const action = useMutation({
    mutationFn: async (command: string) => {
      if (command === 'archive')
        await api.archiveCourse(courseId, { expected_revision: course.data!.revision, reason })
      if (command === 'preview')
        setPlanId((await api.previewRetention({ course_id: courseId, reason })).plan_id)
      if (command === 'confirm')
        setConfirmationId(
          (
            await api.confirmRetention(planId, {
              object_digest: plan.data!.object_digest,
              expected_revision: plan.data!.revision,
              reason,
            })
          ).confirmation_id,
        )
      if (command === 'execute')
        await api.executeRetention(planId, {
          object_digest: plan.data!.object_digest,
          confirmation_id: confirmationId,
          expected_revision: plan.data!.revision,
          reason,
        })
      if (command === 'hold')
        setHoldId(
          (await api.createHold({ object_type: 'course', object_id: courseId, reason })).hold_id,
        )
      if (command === 'close') await api.closeHold(holdId, { expected_revision: 1, reason })
      if (planId) await plan.refetch()
      if (courseId && session.data?.user?.role === 'TEACHER') await course.refetch()
    },
  })
  const admin = session.data?.user?.role === 'ADMIN'
  return (
    <>
      <h1>课程归档与留存</h1>
      <Field label="课程编号" value={courseId} onChange={(e) => setCourseId(e.target.value)} />
      <TextArea
        label="留存操作理由"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        maxLength={500}
      />
      <section className="panel stack">
        <h2>课程状态</h2>
        {course.data && (
          <p>
            {course.data.title} · {course.data.status}
          </p>
        )}
        {!admin && (
          <Button
            disabled={!course.data || !reason.trim()}
            busy={action.isPending}
            onClick={() => action.mutate('archive')}
          >
            确认归档课程
          </Button>
        )}
        <Button
          disabled={!courseId || !reason.trim()}
          busy={action.isPending}
          onClick={() => action.mutate('hold')}
        >
          创建申诉保留
        </Button>
        <Field label="保留记录编号" value={holdId} onChange={(e) => setHoldId(e.target.value)} />
        <Button
          disabled={!holdId || !reason.trim()}
          busy={action.isPending}
          onClick={() => action.mutate('close')}
        >
          确认关闭此保留记录
        </Button>
      </section>
      <section className="panel stack">
        <h2>到期清理</h2>
        {admin && (
          <Button
            disabled={!courseId || !reason.trim()}
            busy={action.isPending}
            onClick={() => action.mutate('preview')}
          >
            生成清理预览
          </Button>
        )}
        <Field label="清理计划编号" value={planId} onChange={(e) => setPlanId(e.target.value)} />
        {plan.data && (
          <>
            <p>
              {plan.data.state} · {plan.data.submission_count} 份提交
            </p>
            <p>
              {plan.data.hold ? '存在申诉保留' : '无申诉保留'} · 到期{' '}
              {plan.data.eligible_at ? beijingTime(plan.data.eligible_at) : '尚未归档'}
            </p>
            <p className="template-text">范围摘要 {plan.data.object_digest}</p>
            {!admin && (
              <Button
                disabled={!reason.trim() || plan.data.state !== 'PREVIEW'}
                busy={action.isPending}
                onClick={() => action.mutate('confirm')}
              >
                教师确认此范围
              </Button>
            )}
            <Field
              label="教师确认编号"
              value={confirmationId}
              onChange={(e) => setConfirmationId(e.target.value)}
            />
            {admin && (
              <Button
                disabled={!confirmationId || !reason.trim() || plan.data.state !== 'CONFIRMED'}
                busy={action.isPending}
                onClick={() => action.mutate('execute')}
              >
                执行已确认的到期清理
              </Button>
            )}
          </>
        )}
        {plan.error && <p role="alert">{plan.error.message}</p>}
      </section>
      {action.error && <p role="alert">{action.error.message}</p>}
      {action.isSuccess && <p role="status">操作已完成。</p>}
    </>
  )
}
