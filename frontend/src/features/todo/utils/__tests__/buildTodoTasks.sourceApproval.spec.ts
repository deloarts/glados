import { describe, expect, it } from 'vitest'

import { buildTodoTasks } from '../buildTodoTasks'
import { Permission } from '@/core/auth/permissions'
import type { OrderResponse } from '@/features/orders'
import type { ProductionOrderResponse } from '@/features/production'
import type { LotSummaryResponse } from '@/features/production'

const NOW = new Date(2026, 7, 3)

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

function lotWith(overrides: Record<string, unknown>): LotSummaryResponse {
  return {
    id: 4,
    lot_number: 'LOT-4',
    status: 'partially_planned',
    priority: 'normal',
    quantity: 1,
    made_item_part_number: 'P-4',
    required_delivery_date: null,
    source_approval_status: 'not_required',
    ...overrides,
  } as unknown as LotSummaryResponse
}

describe('buildTodoTasks - approve_lot_source', () => {
  it('a pending lot yields exactly one approve_lot_source task with the expected shape', () => {
    const tasks = buildTodoTasks({
      ...EMPTY,
      lots: [lotWith({ id: 4, status: 'partially_planned', source_approval_status: 'pending' })],
    })

    const approveTasks = tasks.filter((t) => t.kind === 'approve_lot_source')
    expect(approveTasks).toHaveLength(1)
    const task = approveTasks[0]!
    expect(task.permission).toBe(Permission.MANAGE_LOTS)
    expect(task.bucket).toBe('blockers')
    expect(task.category).toBe('planning')
    expect(task.lotId).toBe(4)
    expect(task.important).toBe(true)
  })

  // A pending DRAFT lot is also unplanned, so both gates fire independently
  // in the same pass: there is no `continue` between them.
  it('a pending DRAFT lot yields both approve_lot_source and plan_lot', () => {
    const tasks = buildTodoTasks({
      ...EMPTY,
      lots: [lotWith({ id: 4, status: 'draft', source_approval_status: 'pending' })],
    })

    expect(tasks.map((t) => t.kind).sort()).toEqual(['approve_lot_source', 'plan_lot'])
  })

  it.each(['completed', 'canceled'])(
    'a pending %s lot yields no approve_lot_source task',
    (status) => {
      const tasks = buildTodoTasks({
        ...EMPTY,
        lots: [lotWith({ id: 4, status, source_approval_status: 'pending' })],
      })

      expect(tasks.map((t) => t.kind)).not.toContain('approve_lot_source')
    },
  )

  it.each(['not_required', 'approved', 'rejected'] as const)(
    'a %s lot yields no approve_lot_source task',
    (status) => {
      const tasks = buildTodoTasks({
        ...EMPTY,
        lots: [lotWith({ id: 4, status: 'partially_planned', source_approval_status: status })],
      })

      expect(tasks.map((t) => t.kind)).not.toContain('approve_lot_source')
    },
  )

  // Undated and status-independent (aside from the completed/canceled
  // exclusion above): a pending on_hold lot still needs an approver, even
  // though on_hold otherwise dominates the rest of the lot loop.
  it('still fires for an on_hold lot, alongside resume_lot', () => {
    const tasks = buildTodoTasks({
      ...EMPTY,
      lots: [lotWith({ id: 4, status: 'on_hold', source_approval_status: 'pending' })],
    })

    expect(tasks.map((t) => t.kind).sort()).toEqual(['approve_lot_source', 'resume_lot'])
    expect(tasks.find((t) => t.kind === 'approve_lot_source')?.dueDate).toBeNull()
  })
})
