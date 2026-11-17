import { describe, it, expect } from 'vitest'

import { moveTargetStatuses, orderItemActionGates } from '../useOrderItemActions'
import type { OrderItemResponse, OrderItemStatus } from '../../types/ordersResponse'

const WRITER = { canWrite: true, canManage: false, canReceiveDeliveries: true }
const MANAGER = { canWrite: true, canManage: true, canReceiveDeliveries: true }
const READER = { canWrite: false, canManage: false, canReceiveDeliveries: false }
// The two halves of the receive:deliveries split, which the backend keeps
// separate from write:orders.
const ORDER_EDITOR = { canWrite: true, canManage: false, canReceiveDeliveries: false }
const RECEIVER = { canWrite: false, canManage: false, canReceiveDeliveries: true }

// What the backend offers on a line in each status, from the order item
// intent table, on an order that is not canceled.
const OFFERED: Record<OrderItemStatus, string[]> = {
  pending: ['mark_requested', 'mark_ordered', 'cancel', 'edit_quantity', 'edit', 'move', 'remove'],
  requested: ['mark_ordered', 'cancel', 'edit_quantity', 'edit', 'move', 'remove'],
  ordered: ['mark_ready_for_pickup', 'deliver', 'cancel', 'edit_quantity', 'edit', 'move'],
  partially_delivered: ['mark_ready_for_pickup', 'deliver', 'correct_delivery', 'close_short', 'edit'],
  delivered: ['correct_delivery', 'edit'],
  canceled: [],
}

function item(overrides: Partial<OrderItemResponse> = {}): OrderItemResponse {
  const status = (overrides.status ?? 'pending') as OrderItemStatus
  return {
    status,
    actions: OFFERED[status],
    expected_pickup_date: null,
    ready_for_pickup_date: null,
    delivery_records: [],
    ...overrides,
  } as OrderItemResponse
}

describe('moveTargetStatuses', () => {
  it('leaves a manager of orders every open order', () => {
    expect(moveTargetStatuses(item({ status: 'ordered' }), true)).toBeUndefined()
  })

  it('offers anyone else only orders the backend lets them change the line on', () => {
    expect(moveTargetStatuses(item({ status: 'pending' }), false)).toEqual([
      'draft',
      'requested',
      'partially_ordered',
    ])
    expect(moveTargetStatuses(item({ status: 'requested' }), false)).toContain('partially_ordered')
    expect(moveTargetStatuses(item({ status: 'ordered' }), false)).toEqual(['draft', 'requested'])
  })
})

describe('orderItemActionGates', () => {
  it('lets a writer edit a line while the line offers it', () => {
    expect(orderItemActionGates.edit(item(), WRITER)).toBe(true)
    expect(orderItemActionGates.edit(item(), READER)).toBe(false)
    // A delivered line a writer may not change is blocked, not offered.
    expect(orderItemActionGates.edit(item({ status: 'delivered', actions: [] }), WRITER)).toBe(false)
    expect(orderItemActionGates.edit(item({ status: 'canceled' }), MANAGER)).toBe(false)
  })

  it('locks the item of a line once goods arrived', () => {
    expect(orderItemActionGates.editIdentity(item({ quantity_delivered: 0 }))).toBe(true)
    expect(orderItemActionGates.editIdentity(item({ quantity_delivered: 2 }))).toBe(false)
  })

  it('lets a writer move a line while the line offers it, as the backend does', () => {
    expect(orderItemActionGates.move(item(), WRITER)).toBe(true)
    expect(orderItemActionGates.move(item({ status: 'requested' }), WRITER)).toBe(true)
    expect(orderItemActionGates.move(item(), MANAGER)).toBe(true)
    expect(orderItemActionGates.move(item(), READER)).toBe(false)
    // Past REQUESTED the backend blocks the move for a writer, so the line
    // leaves it out of its actions.
    expect(orderItemActionGates.move(item({ status: 'ordered', actions: ['deliver'] }), WRITER)).toBe(
      false,
    )
    // A line with pieces received stays on the order that received them.
    expect(orderItemActionGates.move(item({ status: 'partially_delivered' }), MANAGER)).toBe(false)
  })

  it('offers mark-requested only while the line offers it', () => {
    expect(orderItemActionGates.markRequested(item({ status: 'pending' }), WRITER)).toBe(true)
    expect(orderItemActionGates.markRequested(item({ status: 'requested' }), WRITER)).toBe(false)
  })

  it('offers mark-ordered while the line offers it', () => {
    expect(orderItemActionGates.markOrdered(item({ status: 'pending' }), WRITER)).toBe(true)
    expect(orderItemActionGates.markOrdered(item({ status: 'requested' }), WRITER)).toBe(true)
    expect(orderItemActionGates.markOrdered(item({ status: 'ordered' }), WRITER)).toBe(false)
  })

  it('offers ready-for-pickup only once a pickup is expected and not yet flagged', () => {
    const expected = { status: 'ordered' as OrderItemStatus, expected_pickup_date: '2026-01-01' }
    expect(orderItemActionGates.markReadyForPickup(item(expected), WRITER)).toBe(true)
    expect(
      orderItemActionGates.markReadyForPickup(
        item({ ...expected, ready_for_pickup_date: '2026-01-02' }),
        WRITER,
      ),
    ).toBe(false)
    // No pickup expected at all.
    expect(orderItemActionGates.markReadyForPickup(item({ status: 'ordered' }), WRITER)).toBe(
      false,
    )
    // A line the backend does not offer it for, such as a delivered one.
    expect(
      orderItemActionGates.markReadyForPickup(item({ ...expected, status: 'delivered' }), WRITER),
    ).toBe(false)
  })

  it('lets the unit change only until the line received goods', () => {
    expect(orderItemActionGates.editUnit(item({ status: 'ordered', quantity_delivered: 0 }))).toBe(
      true,
    )
    expect(
      orderItemActionGates.editUnit(item({ status: 'partially_delivered', quantity_delivered: 2 })),
    ).toBe(false)
    expect(
      orderItemActionGates.editUnit(
        item({ status: 'ordered', quantity_delivered: 0, quantity_rejected: 1 }),
      ),
    ).toBe(false)
  })

  it('offers deliver only while the line offers it', () => {
    expect(orderItemActionGates.deliver(item({ status: 'ordered' }), WRITER)).toBe(true)
    expect(orderItemActionGates.deliver(item({ status: 'partially_delivered' }), WRITER)).toBe(true)
    expect(orderItemActionGates.deliver(item({ status: 'pending' }), WRITER)).toBe(false)
    expect(orderItemActionGates.deliver(item({ status: 'requested' }), WRITER)).toBe(false)
    expect(orderItemActionGates.deliver(item({ status: 'delivered' }), WRITER)).toBe(false)
    // An ordered line the backend does not offer for delivery, as on a
    // canceled order or a canceled lot, takes none.
    expect(orderItemActionGates.deliver(item({ status: 'ordered', actions: [] }), WRITER)).toBe(
      false,
    )
  })

  it('gates deliver on receive:deliveries, not on write:orders', () => {
    const line = item({ status: 'ordered' })
    // Receiving goods is a warehouse action: an order editor without the
    // permission cannot record one, and a receiving clerk needs nothing else.
    expect(orderItemActionGates.deliver(line, ORDER_EDITOR)).toBe(false)
    expect(orderItemActionGates.deliver(line, RECEIVER)).toBe(true)
  })

  it('gives a receiving clerk no order-editing actions', () => {
    const line = item({ status: 'ordered', expected_pickup_date: '2026-01-01' })
    expect(orderItemActionGates.edit(line, RECEIVER)).toBe(false)
    expect(orderItemActionGates.move(line, RECEIVER)).toBe(false)
    expect(orderItemActionGates.markRequested(line, RECEIVER)).toBe(false)
    expect(orderItemActionGates.markOrdered(line, RECEIVER)).toBe(false)
    expect(orderItemActionGates.markReadyForPickup(line, RECEIVER)).toBe(false)
    expect(orderItemActionGates.cancelLine(line, RECEIVER)).toBe(false)
    expect(orderItemActionGates.closeShort(item({ status: 'partially_delivered' }), RECEIVER)).toBe(
      false,
    )
    expect(orderItemActionGates.remove(line, RECEIVER)).toBe(false)
  })

  it('offers delivery history only when there is any', () => {
    expect(orderItemActionGates.viewHistory(item())).toBe(false)
    expect(
      orderItemActionGates.viewHistory(
        item({ delivery_records: [{ id: 1 }] as OrderItemResponse['delivery_records'] }),
      ),
    ).toBe(true)
  })

  it('removes only a pending or requested line; an ordered one is canceled instead', () => {
    expect(orderItemActionGates.remove(item({ status: 'requested' }), WRITER)).toBe(true)
    expect(orderItemActionGates.remove(item({ status: 'ordered' }), WRITER)).toBe(false)
    expect(orderItemActionGates.cancelLine(item({ status: 'ordered' }), WRITER)).toBe(true)
    expect(orderItemActionGates.remove(item({ status: 'partially_delivered' }), WRITER)).toBe(false)
    expect(orderItemActionGates.remove(item({ status: 'delivered' }), WRITER)).toBe(false)
  })

  it('closes a partly delivered line short instead of canceling it', () => {
    const partial = item({ status: 'partially_delivered' })
    expect(orderItemActionGates.closeShort(partial, WRITER)).toBe(true)
    expect(orderItemActionGates.cancelLine(partial, WRITER)).toBe(false)
    expect(orderItemActionGates.closeShort(item({ status: 'ordered' }), WRITER)).toBe(false)
  })

  it('locks the quantity of a line that is no longer open', () => {
    expect(orderItemActionGates.editQuantity(item({ status: 'ordered' }))).toBe(true)
    expect(orderItemActionGates.editQuantity(item({ status: 'partially_delivered' }))).toBe(false)
  })

  it('offers a correction on an accepted delivery row to a receiver, never on a correction', () => {
    const delivered = item({ status: 'delivered' })
    expect(orderItemActionGates.correctDelivery(delivered, { quantity: 4 }, RECEIVER)).toBe(true)
    expect(
      orderItemActionGates.correctDelivery(
        delivered,
        { quantity: -1, corrects_delivery_id: 7 },
        RECEIVER,
      ),
    ).toBe(false)
    // A row that booked only rejected pieces has nothing accepted to take back.
    expect(orderItemActionGates.correctDelivery(delivered, { quantity: 0 }, RECEIVER)).toBe(false)
    expect(orderItemActionGates.correctDelivery(delivered, { quantity: 4 }, ORDER_EDITOR)).toBe(
      false,
    )
    expect(
      orderItemActionGates.correctDelivery(item({ status: 'ordered' }), { quantity: 4 }, RECEIVER),
    ).toBe(false)
  })

  it('offers a writer no line change on a submitted order, as its actions leave them out', () => {
    // Past REQUESTED the backend offers line changes to a manager of orders
    // only, so a writer's ordered and partly delivered lines carry just the
    // delivery actions.
    const ordered = item({ status: 'ordered', actions: ['deliver'] })
    const partial = item({ status: 'partially_delivered', actions: ['deliver', 'correct_delivery'] })
    expect(orderItemActionGates.cancelLine(ordered, WRITER)).toBe(false)
    expect(orderItemActionGates.move(ordered, MANAGER)).toBe(false)
    expect(orderItemActionGates.editQuantity(ordered)).toBe(false)
    expect(orderItemActionGates.closeShort(partial, WRITER)).toBe(false)
    expect(orderItemActionGates.remove(item({ status: 'requested', actions: [] }), WRITER)).toBe(
      false,
    )
    expect(orderItemActionGates.deliver(ordered, WRITER)).toBe(true)
  })

  it('denies every write action to a read-only user', () => {
    const line = item({ status: 'ordered', expected_pickup_date: '2026-01-01' })
    expect(orderItemActionGates.edit(line, READER)).toBe(false)
    expect(orderItemActionGates.move(line, READER)).toBe(false)
    expect(orderItemActionGates.markRequested(line, READER)).toBe(false)
    expect(orderItemActionGates.markOrdered(line, READER)).toBe(false)
    expect(orderItemActionGates.markReadyForPickup(line, READER)).toBe(false)
    expect(orderItemActionGates.deliver(line, READER)).toBe(false)
    expect(orderItemActionGates.cancelLine(line, READER)).toBe(false)
    expect(orderItemActionGates.remove(line, READER)).toBe(false)
  })
})
