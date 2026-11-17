import { describe, expect, it } from 'vitest'

import { buildTodoTasks } from '../buildTodoTasks'
import type { MeetingTodoSourceResponse } from '../../types/todoSourcesResponse'
import type { OrderResponse } from '@/features/orders'
import type { LotSummaryResponse, ProductionOrderResponse } from '@/features/production'

const NOW = new Date(2026, 10, 10)

const EMPTY = {
  orders: [] as OrderResponse[],
  boughtDemands: [],
  madeDemands: [],
  sourceDemands: [],
  productionOrders: [] as ProductionOrderResponse[],
  productionSchedule: new Map(),
  lots: [] as LotSummaryResponse[],
  madeItemLabel: (partNumber: string, revision: string) => `${partNumber}:${revision}`,
  now: NOW,
}

function meetingTodo(overrides: Partial<MeetingTodoSourceResponse> = {}): MeetingTodoSourceResponse {
  return {
    todo_id: 11,
    title: 'Send layout drawing rev. D',
    due_date: '2026-11-13',
    meeting_id: 21,
    meeting_number: 'MTG-26-0021',
    meeting_name: 'Design Review Gripper',
    card_id: 4,
    card_scope: 'Vacuum gripper',
    owner_kind: 'project',
    owner_id: 142,
    ...overrides,
  }
}

function build(todos: MeetingTodoSourceResponse[]) {
  return buildTodoTasks({ ...EMPTY, meetingTodos: todos })
}

describe('buildTodoTasks meeting todos', () => {
  it('turns an open meeting todo into a task of the Meetings category that opens its card', () => {
    const [task] = build([meetingTodo()])

    expect(task).toMatchObject({
      id: 'meeting-todo-11',
      kind: 'meeting_todo',
      category: 'meetings',
      bucket: 'week',
      titleKey: 'todo.tasks.meetingTodo.title',
      titleParams: { title: 'Send layout drawing rev. D' },
      subtitleKey: 'todo.tasks.meetingTodo.subtitle',
      subtitleParams: { meetingNumber: 'MTG-26-0021', meetingName: 'Design Review Gripper', scope: 'Vacuum gripper' },
      route: '/meetings/21#card-4',
      permission: null,
    })
    expect(task?.dueDate?.getTime()).toBe(new Date(2026, 10, 13).getTime())
  })

  it('buckets the todos by due date like every other task', () => {
    const tasks = build([
      meetingTodo({ todo_id: 1, due_date: '2026-11-09' }),
      meetingTodo({ todo_id: 2, due_date: '2026-11-10' }),
      meetingTodo({ todo_id: 3, due_date: '2026-11-15' }),
      meetingTodo({ todo_id: 4, due_date: null }),
      meetingTodo({ todo_id: 5, due_date: '2026-12-20' }),
    ])

    expect(Object.fromEntries(tasks.map((task) => [task.id, task.bucket]))).toEqual({
      'meeting-todo-1': 'overdue',
      'meeting-todo-2': 'today',
      'meeting-todo-3': 'week',
      'meeting-todo-4': 'blockers',
    })
    // Every one of them is the user's own, so each shows while Show All is off.
    expect(tasks.every((task) => task.important)).toBe(true)
  })

  it('counts every meeting todo as important, due later this week or undated', () => {
    const tasks = build([meetingTodo({ todo_id: 1, due_date: '2026-11-15' }), meetingTodo({ todo_id: 2, due_date: null })])

    expect(tasks.map((task) => [task.bucket, task.important])).toEqual([
      ['week', true],
      ['blockers', true],
    ])
  })

  it('names only the meeting when the card has no scope', () => {
    const [task] = build([meetingTodo({ card_scope: null })])

    expect(task?.subtitleKey).toBe('todo.tasks.meetingTodo.subtitleNoScope')
    expect(task?.subtitleParams).toMatchObject({ meetingNumber: 'MTG-26-0021', meetingName: 'Design Review Gripper' })
  })

  it('gives no meeting tasks while the sources carry no meeting todos', () => {
    expect(buildTodoTasks(EMPTY)).toEqual([])
  })
})
