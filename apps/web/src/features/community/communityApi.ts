import { api } from '../../app/runtime'
export type Thread = {
  thread_id: string
  course_id: string
  problem_id: string
  version_id: string
  title: string
  body: string
  author_name: string
  is_mine: boolean
  can_moderate: boolean
  resolved: boolean
  locked: boolean
  pinned: boolean
  hidden: boolean
  revision: number
  reply_count: number
  created_at: string
  updated_at: string
}
export type Reply = {
  reply_id: string
  thread_id: string
  body: string
  author_name: string
  is_mine: boolean
  hidden: boolean
  revision: number
  created_at: string
}
export type Leaderboard = {
  course_id: string
  kind: 'progress' | 'grades'
  updated_at: string
  included_assignments: number
  show_name: boolean
  items: { entry_id: string; rank: number; display_name: string; value: number; is_me: boolean }[]
  next_cursor: string | null
}
export type ThreadChange = {
  expected_revision: number
  reason: string
  resolved?: boolean
  locked?: boolean
  pinned?: boolean
  hidden?: boolean
}
export function discussionPath(course: string, problem: string, version: string) {
  return `/courses/${encodeURIComponent(course)}/problems/${encodeURIComponent(problem)}/discussions?version_id=${encodeURIComponent(version)}`
}
function cursorQuery(cursor?: string) {
  return cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''
}
export const communityApi = {
  leaderboard: (id: string, kind: 'progress' | 'grades', cursor?: string) =>
    api.request<Leaderboard>(
      'GET',
      `/courses/${encodeURIComponent(id)}/leaderboard?kind=${kind}${cursorQuery(cursor)}`,
    ),
  preference: (id: string, show_name: boolean) =>
    api.request<{ show_name: boolean }>(
      'PATCH',
      `/courses/${encodeURIComponent(id)}/leaderboard-preference`,
      { show_name },
    ),
  discussions: (id: string, problem: string, version: string, cursor?: string) =>
    api.request<{ items: Thread[]; next_cursor: string | null }>(
      'GET',
      discussionPath(id, problem, version) + cursorQuery(cursor),
    ),
  create: (
    id: string,
    problem: string,
    body: { version_id: string; title: string; body: string },
  ) =>
    api.request<Thread>(
      'POST',
      `/courses/${encodeURIComponent(id)}/problems/${encodeURIComponent(problem)}/discussions`,
      body,
    ),
  discussion: (id: string, cursor?: string) =>
    api.request<{ thread: Thread; replies: Reply[]; next_cursor: string | null }>(
      'GET',
      `/discussions/${encodeURIComponent(id)}?limit=30${cursorQuery(cursor)}`,
    ),
  reply: (id: string, body: string) =>
    api.request<Reply>('POST', `/discussions/${encodeURIComponent(id)}/replies`, { body }),
  update: (id: string, body: ThreadChange) =>
    api.request<Thread>('PATCH', `/discussions/${encodeURIComponent(id)}`, body),
  updateReply: (id: string, body: { expected_revision: number; hidden: boolean; reason: string }) =>
    api.request<Reply>('PATCH', `/discussion-replies/${encodeURIComponent(id)}`, body),
}
