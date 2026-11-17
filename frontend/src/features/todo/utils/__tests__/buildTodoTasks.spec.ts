import { describe, expect, it } from 'vitest'

import { buildTodoTasks, sortTodoTasks } from '../buildTodoTasks'
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
  // Plain concatenation is enough here; this suite doesn't exercise a
  // configured separator, that's madeItemLabel.spec.ts's job.
  madeItemLabel: (partNumber: string, revision: string) => `${partNumber}:${revision}`,
  now: NOW,
}

function orderWith(
  itemOverrides: Record<string, unknown>,
  orderOverrides: Record<string, unknown> = {},
): OrderResponse {
  return {
    id: 1,
    order_number: 'ORD-1',
    status: 'ordered',
    supplier_name: 'ACME',
    items: [
      {
        id: 10,
        status: 'ordered',
        item_article_name: 'Widget',
        supplier_name: 'ACME',
        quantity: 5,
        quantity_delivered: 0,
        expected_pickup_date: null,
        ready_for_pickup_date: null,
        expected_delivery_date: null,
        ...itemOverrides,
      },
    ],
    ...orderOverrides,
  } as unknown as OrderResponse
}

describe('buildTodoTasks', () => {
  it('turns a ready-for-pickup item into a collect task due on its ready date', () => {
    const tasks = buildTodoTasks({
      ...EMPTY,
      orders: [orderWith({ ready_for_pickup_date: '2026-08-03' })],
    })
    const task = tasks.find((t) => t.kind === 'collect_pickup')
    expect(task).toBeDefined()
    expect(task?.bucket).toBe('today')
  })

  // ready_for_pickup_date is a full timestamp since the event-timestamp
  // widening, so the bucket must come from the DAY it falls on rather than
  // the raw instant: a 14:30 confirmation is still due "today".
  it('buckets a timestamped ready-for-pickup date by its day, not its clock time', () => {
    const tasks = buildTodoTasks({
      ...EMPTY,
      orders: [orderWith({ ready_for_pickup_date: '2026-08-03T14:30:00+00:00' })],
    })
    const task = tasks.find((t) => t.kind === 'collect_pickup')
    expect(task).toBeDefined()
    expect(task?.bucket).toBe('today')
  })

  it('treats a timestamped pickup date from an earlier day as overdue', () => {
    const tasks = buildTodoTasks({
      ...EMPTY,
      orders: [orderWith({ ready_for_pickup_date: '2026-08-01T23:45:00+00:00' })],
    })
    expect(tasks.find((t) => t.kind === 'collect_pickup')?.bucket).toBe('overdue')
  })

  it('asks to chase the supplier when a pickup is expected but not yet confirmed ready', () => {
    const tasks = buildTodoTasks({
      ...EMPTY,
      orders: [orderWith({ expected_pickup_date: '2026-08-03' })],
    })
    expect(tasks.map((t) => t.kind)).toContain('confirm_pickup')
  })

  // A collectable item must never also appear as a "chase the delivery" task:
  // it's the same physical goods, and pickup is the actionable framing.
  it('prefers the pickup task over a delivery task for the same item', () => {
    const tasks = buildTodoTasks({
      ...EMPTY,
      orders: [
        orderWith({ ready_for_pickup_date: '2026-08-01', expected_delivery_date: '2026-07-01' }),
      ],
    })
    expect(tasks.map((t) => t.kind)).toEqual(['collect_pickup'])
  })

  it('only raises a delivery task once it is actually late', () => {
    const late = buildTodoTasks({
      ...EMPTY,
      orders: [orderWith({ expected_delivery_date: '2026-07-20' })],
    })
    expect(late.find((t) => t.kind === 'chase_delivery')?.bucket).toBe('overdue')

    const future = buildTodoTasks({
      ...EMPTY,
      orders: [orderWith({ expected_delivery_date: '2026-08-20' })],
    })
    expect(future.map((t) => t.kind)).not.toContain('chase_delivery')
  })

  it('ignores items that are already delivered or canceled', () => {
    for (const status of ['delivered', 'canceled']) {
      const tasks = buildTodoTasks({
        ...EMPTY,
        orders: [orderWith({ status, ready_for_pickup_date: '2026-08-01' })],
      })
      expect(tasks).toEqual([])
    }
  })

  it('files undated work under blockers rather than inventing a due date', () => {
    const tasks = buildTodoTasks({ ...EMPTY, orders: [orderWith({}, { status: 'draft' })] })
    const task = tasks.find((t) => t.kind === 'submit_order')
    expect(task?.bucket).toBe('blockers')
    expect(task?.dueDate).toBeNull()
  })

  it('drops work due beyond the coming week', () => {
    const tasks = buildTodoTasks({
      ...EMPTY,
      orders: [orderWith({ ready_for_pickup_date: '2026-09-30' })],
    })
    expect(tasks).toEqual([])
  })

  it('raises only human-resolvable production conflicts', () => {
    const productionOrder = {
      id: 5,
      status: 'queued',
      lot_id: 7,
      lot_number: 'LOT-1',
      production_order_number: 'PO-1',
      made_item_part_number: 'P-1',
      machine_internal_name: 'CNC1',
      lot_position_sequence: 1,
      lot_position_count: 1,
      priority: 'normal',
      // waiting_on_predecessor resolves itself as the schedule advances, so
      // it is not something a person can act on.
      conflicts: ['uncategorized_step', 'waiting_on_predecessor'],
    } as unknown as ProductionOrderResponse

    const tasks = buildTodoTasks({ ...EMPTY, productionOrders: [productionOrder] })
    const conflictTasks = tasks.filter((t) => t.kind === 'production_conflict')
    expect(conflictTasks).toHaveLength(1)
    expect(conflictTasks[0]?.titleKey).toContain('uncategorized_step')
  })

  it('chases a part-delivered item without waiting for its date to pass', () => {
    const tasks = buildTodoTasks({
      ...EMPTY,
      orders: [
        orderWith({
          quantity: 5,
          quantity_delivered: 2,
          status: 'partially_delivered',
          expected_delivery_date: '2026-08-20',
        }),
      ],
    })
    expect(tasks.map((t) => t.kind)).toContain('chase_partial_delivery')
  })

  it('always surfaces a held lot and a job stalled on material, undated', () => {
    const heldLot = buildTodoTasks({
      ...EMPTY,
      lots: [
        {
          id: 3,
          lot_number: 'LOT-9',
          status: 'on_hold',
          priority: 'normal',
          quantity: 4,
          made_item_part_number: 'P-9',
          required_delivery_date: null,
        } as unknown as LotSummaryResponse,
      ],
    })
    const held = heldLot.find((t) => t.kind === 'resume_lot')
    expect(held?.bucket).toBe('blockers')
    expect(held?.important).toBe(true)

    const stalled = buildTodoTasks({
      ...EMPTY,
      productionOrders: [
        {
          id: 6,
          status: 'queued',
          lot_id: 3,
          lot_number: 'LOT-9',
          production_order_number: 'PO-9',
          made_item_part_number: 'P-9',
          priority: 'normal',
          waiting_on_raw_material: true,
          conflicts: [],
        } as unknown as ProductionOrderResponse,
      ],
    })
    expect(stalled.find((t) => t.kind === 'chase_raw_material')?.important).toBe(true)
  })

  // Drives the "Show all" toggle: routine, non-urgent work must be
  // excluded by default or the page stops being a shortlist.
  it('marks due-now and flagged work important, but not routine future work', () => {
    const dueToday = buildTodoTasks({
      ...EMPTY,
      orders: [orderWith({ ready_for_pickup_date: '2026-08-03' })],
    })
    expect(dueToday[0]?.important).toBe(true)

    const nextWeek = buildTodoTasks({
      ...EMPTY,
      orders: [orderWith({ ready_for_pickup_date: '2026-08-08' })],
    })
    expect(nextWeek[0]?.bucket).toBe('week')
    expect(nextWeek[0]?.important).toBe(false)
  })

  // Drives the category filter. The split is by who does the work, so a
  // stalled job belongs with the shop floor even though fixing it is a
  // procurement job, and lot planning is never mixed in with it.
  it('categorises tasks by the role that acts on them', () => {
    const procurement = buildTodoTasks({
      ...EMPTY,
      orders: [orderWith({ ready_for_pickup_date: '2026-08-03' })],
    })
    expect(procurement[0]?.category).toBe('procurement')

    const stalled = buildTodoTasks({
      ...EMPTY,
      productionOrders: [
        {
          id: 6,
          status: 'queued',
          lot_id: 3,
          lot_number: 'LOT-9',
          production_order_number: 'PO-9',
          made_item_part_number: 'P-9',
          priority: 'normal',
          waiting_on_raw_material: true,
          conflicts: ['uncategorized_step'],
        } as unknown as ProductionOrderResponse,
      ],
    })
    expect(stalled.find((t) => t.kind === 'chase_raw_material')?.category).toBe('shop_floor')
    expect(stalled.find((t) => t.kind === 'production_conflict')?.category).toBe('planning')

    const planning = buildTodoTasks({
      ...EMPTY,
      lots: [
        {
          id: 4,
          lot_number: 'LOT-4',
          status: 'draft',
          priority: 'normal',
          quantity: 1,
          made_item_part_number: 'P-4',
          required_delivery_date: null,
        } as unknown as LotSummaryResponse,
      ],
    })
    expect(planning[0]?.category).toBe('planning')
  })

  it('sorts overdue before today, and flagged priority before the rest', () => {
    const tasks = buildTodoTasks({
      ...EMPTY,
      orders: [
        orderWith({ id: 1, ready_for_pickup_date: '2026-08-03' }),
        orderWith({ id: 2, ready_for_pickup_date: '2026-07-30' }, { id: 2 }),
      ],
    })
    const sorted = sortTodoTasks(tasks)
    expect(sorted[0]?.bucket).toBe('overdue')
    expect(sorted[1]?.bucket).toBe('today')
  })
})
