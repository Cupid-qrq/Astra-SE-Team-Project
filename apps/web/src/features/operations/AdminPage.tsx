import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { api } from '../../app/runtime'
import { Field } from '../../components/ui/Field'
import { Button } from '../../components/ui/Button'
import { TextArea } from '../../components/ui/TextArea'
import { StatePanel } from '../../components/ui/StatePanel'
import { fromBeijing, beijingTime } from '../assignments/time'

export function AdminPage() {
  const cache = useQueryClient()
  const [tab, setTab] = useState('health')
  const [reason, setReason] = useState('')
  const [password, setPassword] = useState('')
  const [assignmentIds, setAssignmentIds] = useState('')
  const [started, setStarted] = useState('')
  const [batchId, setBatchId] = useState('')
  const [batchRevision, setBatchRevision] = useState('1')
  const health = useQuery({
    queryKey: ['admin-health'],
    queryFn: api.adminHealth,
    enabled: tab === 'health',
    refetchInterval: 10000,
  })
  const users = useInfiniteQuery({
    queryKey: ['admin-users'],
    queryFn: ({ pageParam }) => api.adminUsers(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
    enabled: tab === 'users',
  })
  const jobs = useInfiniteQuery({
    queryKey: ['admin-jobs'],
    queryFn: ({ pageParam }) => api.adminJobs(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
    enabled: tab === 'jobs',
  })
  const incidents = useInfiniteQuery({
    queryKey: ['incidents'],
    queryFn: ({ pageParam }) => api.incidents(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
    enabled: tab === 'incidents',
  })
  const audit = useInfiniteQuery({
    queryKey: ['audit'],
    queryFn: ({ pageParam }) => api.auditEvents(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (p) => p.next_cursor || undefined,
    enabled: tab === 'audit',
  })
  const action = useMutation({
    mutationFn: async (run: () => Promise<unknown>) => run(),
    onSuccess: async () => {
      setPassword('')
      await cache.invalidateQueries({ queryKey: ['admin-users'] })
      await cache.invalidateQueries({ queryKey: ['admin-jobs'] })
      await cache.invalidateQueries({ queryKey: ['incidents'] })
    },
  })
  function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    action.mutate(
      () =>
        api.createUser({
          login_name: String(data.get('login')),
          display_name: String(data.get('display')),
          role: String(data.get('role')) as 'STUDENT' | 'TEACHER' | 'ADMIN',
          initial_password: password,
          reason,
        }),
      { onSuccess: () => form.reset() },
    )
  }
  return (
    <>
      <h1>平台管理</h1>
      <div className="filters" role="group" aria-label="管理栏目">
        {[
          ['health', '运行状态'],
          ['users', '账号'],
          ['jobs', '评测任务'],
          ['incidents', '故障事件'],
          ['audit', '审计'],
        ].map(([key, label]) => (
          <Button key={key} onClick={() => setTab(key!)}>
            {label}
          </Button>
        ))}
      </div>
      <TextArea
        label="管理操作理由"
        hint={tab === 'users' ? '账号操作请填写 10–500 字的理由。' : undefined}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        maxLength={500}
      />
      {action.error && <p role="alert">{action.error.message}</p>}
      {action.isSuccess && <p role="status">操作已完成。</p>}
      {tab === 'health' &&
        (health.data ? (
          <section className="panel stack">
            <p>数据库 {health.data.database}</p>
            <p>处理中提交 {health.data.pending} / 100</p>
            <p>执行槽 {health.data.slot_state}</p>
            <p>磁盘可用 {Math.round(health.data.disk_free_bytes / 1024 ** 3)} GiB</p>
            <p>
              时钟偏差 {health.data.clock_skew_ms} ms
              {health.data.clock_skew_ms > 1000 ? ' · 时钟偏差告警' : ''}
            </p>
            {health.data.budget.map((row) => (
              <p key={row.scope}>
                {row.scope} 预算 {row.limit}，已结算 {row.settled}，预留 {row.reserved}，未知费用{' '}
                {row.uncertain}
              </p>
            ))}
          </section>
        ) : (
          <StatePanel
            kind={health.isError ? 'error' : 'loading'}
            title="读取运行状态"
            description={health.error?.message}
          />
        ))}
      {tab === 'users' && (
        <>
          <form className="panel stack" onSubmit={createUser}>
            <h2>创建账号</h2>
            <Field label="登录账号" name="login" required />
            <Field label="显示名称" name="display" required />
            <label>
              角色
              <select name="role">
                <option value="STUDENT">学生</option>
                <option value="TEACHER">教师</option>
                <option value="ADMIN">管理员</option>
              </select>
            </label>
            <Field
              label="初始或重置密码"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={12}
              autoComplete="new-password"
            />
            <Button
              type="submit"
              disabled={[...reason.trim()].length < 10 || password.length < 12}
              busy={action.isPending}
            >
              创建账号
            </Button>
          </form>
          {users.error && <p role="alert">{users.error.message}</p>}
          {users.data?.pages
            .flatMap((p) => p.items)
            .map((user) => (
              <article className="panel stack" key={user.user_id}>
                <h3>
                  {user.display_name} · {user.login_name}
                </h3>
                <p>
                  {user.role} · {user.status}
                </p>
                <Button
                  disabled={[...reason.trim()].length < 10}
                  busy={action.isPending}
                  onClick={() =>
                    action.mutate(() =>
                      api.updateUser(user.user_id, {
                        status: user.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE',
                        expected_revision: user.revision,
                        reason,
                      }),
                    )
                  }
                >
                  {user.status === 'ACTIVE' ? '停用账号' : '恢复账号'}
                </Button>
                <Button
                  disabled={[...reason.trim()].length < 10 || password.length < 12}
                  busy={action.isPending}
                  onClick={() =>
                    action.mutate(() =>
                      api.resetUserPassword(user.user_id, {
                        one_time_password: password,
                        expected_revision: user.revision,
                        reason,
                      }),
                    )
                  }
                >
                  重置为上方密码并撤销会话
                </Button>
              </article>
            ))}
          {users.hasNextPage && (
            <Button onClick={() => void users.fetchNextPage()}>加载更多账号</Button>
          )}
        </>
      )}
      {tab === 'jobs' && (
        <>
          {jobs.error && <p role="alert">{jobs.error.message}</p>}
          {jobs.data?.pages
            .flatMap((p) => p.items)
            .map((job) => (
              <article className="panel stack" key={job.job_id}>
                <p className="template-text">提交 {job.submission_id}</p>
                <p>
                  {job.kind} · {job.state} · {job.verdict || '处理中'}
                </p>
                {job.verdict === 'SE' && !job.batch_id && (
                  <Button
                    disabled={!reason.trim()}
                    busy={action.isPending}
                    onClick={() =>
                      action.mutate(() =>
                        api.retrySubmission(job.submission_id, {
                          expected_revision: job.revision,
                          reason,
                        }),
                      )
                    }
                  >
                    人工重试当前平台故障
                  </Button>
                )}
              </article>
            ))}
          {jobs.hasNextPage && (
            <Button onClick={() => void jobs.fetchNextPage()}>加载更多任务</Button>
          )}
          <section className="panel stack">
            <h2>重试失败批次</h2>
            <Field
              label="失败批次编号"
              value={batchId}
              onChange={(event) => setBatchId(event.target.value)}
            />
            <Field
              label="批次修订号"
              type="number"
              min={1}
              value={batchRevision}
              onChange={(event) => setBatchRevision(event.target.value)}
            />
            <Button
              disabled={!reason.trim() || !batchId}
              busy={action.isPending}
              onClick={() =>
                action.mutate(() =>
                  api.retryRejudge(batchId, { expected_revision: Number(batchRevision), reason }),
                )
              }
            >
              重试失败成员
            </Button>
          </section>
        </>
      )}
      {tab === 'incidents' && (
        <>
          <section className="panel stack">
            <h2>登记平台故障</h2>
            <Field
              label="影响作业编号（逗号分隔）"
              value={assignmentIds}
              onChange={(event) => setAssignmentIds(event.target.value)}
            />
            <Field
              label="故障开始时间（北京时间）"
              type="datetime-local"
              value={started}
              onChange={(event) => setStarted(event.target.value)}
            />
            <Button
              disabled={!reason.trim() || !started || !assignmentIds}
              busy={action.isPending}
              onClick={() =>
                action.mutate(() =>
                  api.createIncident({
                    assignment_ids: assignmentIds.split(',').map((s) => s.trim()),
                    started_at: fromBeijing(started),
                    reason_code: 'JUDGE_UNAVAILABLE',
                    reason,
                    evidence_refs: [],
                    evidence_incomplete: true,
                  }),
                )
              }
            >
              登记并通知教师裁决
            </Button>
          </section>
          {incidents.hasNextPage && (
            <Button
              busy={incidents.isFetchingNextPage}
              onClick={() => void incidents.fetchNextPage()}
            >
              加载更多公平事件
            </Button>
          )}
          {incidents.error && <p role="alert">{incidents.error.message}</p>}
          {incidents.data?.pages
            .flatMap((page) => page.items)
            .map((event) => (
              <article className="panel stack" key={event.incident_id}>
                <p className="template-text">事件 {event.incident_id}</p>
                <p>
                  开始 {beijingTime(event.started_at)} ·{' '}
                  {event.recovered_at ? '已恢复' : '尚未恢复'}
                </p>
                {!event.recovered_at && (
                  <Button
                    disabled={!reason.trim()}
                    busy={action.isPending}
                    onClick={() =>
                      action.mutate(() =>
                        api.adminHealth().then((health) =>
                          api.recoverIncident(event.incident_id, {
                            recovered_at: health.server_time,
                            expected_revision: event.revision,
                            reason,
                          }),
                        ),
                      )
                    }
                  >
                    确认现已恢复
                  </Button>
                )}
              </article>
            ))}
        </>
      )}
      {tab === 'audit' && (
        <>
          {audit.error && <p role="alert">{audit.error.message}</p>}
          {audit.data?.pages
            .flatMap((p) => p.items)
            .map((event) => (
              <article className="panel stack" key={event.event_id}>
                <p>
                  {beijingTime(event.timestamp)} · {event.action}
                </p>
                <p className="template-text">对象 {event.object_id}</p>
                <p>{event.reason}</p>
              </article>
            ))}
          {audit.hasNextPage && (
            <Button onClick={() => void audit.fetchNextPage()}>加载更多审计记录</Button>
          )}
        </>
      )}
    </>
  )
}
