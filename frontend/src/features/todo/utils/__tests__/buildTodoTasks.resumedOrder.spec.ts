import { describe, expect, it } from 'vitest'

import { buildTodoTasks } from '../buildTodoTasks'
import { computeProductionSchedule } from '@/features/production'
import type { OrderResponse } from '@/features/orders'
import type { ProductionOrderResponse } from '@/features/production'
import type { LotSummaryResponse } from '@/features/production'

// Wednesday noon, local time.
const NOW = new Date(2026, 7, 5, 12, 0)

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

function localInstant(day: number, hour: number): string {
  return new Date(2026, 7, day, hour, 0).toISOString()
}

// Started on Monday, resumed this morning and paused again before noon.
function orderPausedAgainToday(): ProductionOrderResponse {
  return {
    id: 7,
    production_order_number: 'PO-7',
    status: 'paused',
    priority: 'normal',
    pinned: false,
    queue_sequence: 1,
    quantity: 10,
    quantity_completed: 0,
    estimated_duration_minutes: 240,
    planned_start: null,
    planned_end: null,
    not_before: null,
    actual_start: localInstant(3, 8),
    actual_end: null,
    machine_id: 1,
    machine_internal_name: 'Machine 1',
    lot_position_id: 1,
    lot_id: 4,
    lot_number: 'LOT-4',
    made_item_part_number: 'P-4',
    made_item_revision: 'A',
    lot_position_sequence: 1,
    lot_position_count: 1,
    waiting_on_raw_material: false,
    conflicts: [],
    interruptions: [
      { paused_at: localInstant(3, 10), resumed_at: localInstant(5, 9) },
      { paused_at: localInstant(5, 11), resumed_at: null },
    ],
  } as unknown as ProductionOrderResponse
}

describe('buildTodoTasks - start_production_order for a resumed order', () => {
  it('dates the restart of an order paused again today by its latest resume, not its first start', () => {
    const order = orderPausedAgainToday()
    const productionSchedule = computeProductionSchedule({
      machines: [{ id: 1, internal_name: 'Machine 1' }],
      orders: [order],
      lots: [],
      orderedDateByPositionId: new Map(),
      now: NOW,
    })

    const tasks = buildTodoTasks({ ...EMPTY, productionOrders: [order], productionSchedule })

    const [task] = tasks.filter((t) => t.kind === 'start_production_order')
    expect(task?.dueDate).toEqual(new Date(2026, 7, 5))
    expect(task?.bucket).toBe('today')
  })
})
