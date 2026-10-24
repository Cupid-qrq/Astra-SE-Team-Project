import type { components } from '../lib/api/schema'
export const courseId = '11111111-1111-4111-8111-111111111111'
export const teacherId = '22222222-2222-4222-8222-222222222222'
export const user: components['schemas']['User'] = {
  user_id: '33333333-3333-4333-8333-333333333333',
  login_name: 'demo_student',
  display_name: '林同学',
  role: 'STUDENT',
  status: 'ACTIVE',
  must_change_password: false,
  revision: 1,
}
export const courses: components['schemas']['Course'][] = [
  {
    course_id: courseId,
    teacher_id: teacherId,
    title: '程序设计基础',
    status: 'ACTIVE',
    revision: 1,
  },
  {
    course_id: '44444444-4444-4444-8444-444444444444',
    teacher_id: teacherId,
    title: '数据结构与算法',
    status: 'ACTIVE',
    revision: 1,
  },
  {
    course_id: '55555555-5555-4555-8555-555555555555',
    teacher_id: teacherId,
    title: 'Python 程序设计',
    status: 'ARCHIVED',
    revision: 1,
  },
]
export const assignments: components['schemas']['AssignmentSummary'][] = [
  {
    assignment_id: '66666666-6666-4666-8666-666666666666',
    course_id: courseId,
    title: '分支与循环',
    open_at: '2026-10-20T00:00:00.000Z',
    due_at: '2026-10-28T15:59:00.000Z',
    state: 'OPEN',
    revision: 1,
  },
  {
    assignment_id: '77777777-7777-4777-8777-777777777777',
    course_id: courseId,
    title: '数组与字符串',
    open_at: '2026-10-29T00:00:00.000Z',
    due_at: '2026-11-05T15:59:00.000Z',
    state: 'SCHEDULED',
    revision: 1,
  },
  {
    assignment_id: '88888888-8888-4888-8888-888888888888',
    course_id: courseId,
    title: '输入、输出与表达式',
    open_at: '2026-10-10T00:00:00.000Z',
    due_at: '2026-10-18T15:59:00.000Z',
    state: 'CLOSED',
    revision: 1,
  },
]
