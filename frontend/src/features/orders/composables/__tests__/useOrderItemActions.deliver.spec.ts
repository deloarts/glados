import { describe, it, expect } from 'vitest'

import { hasDeliverableLines, isDeliverableLine, orderItemActionGates } from '../useOrderItemActions'
import type { OrderItemResponse, OrderResponse } from '../../types/ordersResponse'

const RECEIVER = { canWrite: false, canManage: false, canReceiveDeliveries: true }
const ORDER_MANAGER = { canWrite: true, canManage: true, canReceiveDeliveries: false }

// The backend offers deliver on a line that is ordered or partially
// delivered, on an order that is not canceled, and for a MADE line on a lot
// that is not canceled; the gates only read what it offers.
function line(actions: string[]): OrderItemResponse {
  return { status: 'ordered', actions } as OrderItemResponse
}

function order(lines: OrderItemResponse[]): OrderResponse {
  return { status: 'ordered', items: lines } as OrderResponse
}

describe('isDeliverableLine', () => {
  it('accepts a line whose actions offer a delivery', () => {
    expect(isDeliverableLine(line(['deliver', 'close_short']))).toBe(true)
  })

  it('refuses a line whose actions do not, whatever its status', () => {
    expect(isDeliverableLine(line(['cancel', 'mark_ordered']))).toBe(false)
    expect(isDeliverableLine({ status: 'ordered' } as OrderItemResponse)).toBe(false)
  })
})

describe('hasDeliverableLines', () => {
  it('finds a deliverable line among the others', () => {
    expect(hasDeliverableLines(order([line(['remove']), line(['deliver'])]))).toBe(true)
  })

  it('finds nothing when no line offers a delivery', () => {
    expect(hasDeliverableLines(order([line(['remove']), line([])]))).toBe(false)
  })

  it('finds nothing on an order without lines', () => {
    expect(hasDeliverableLines(order([]))).toBe(false)
  })
})

describe('orderItemActionGates.deliver', () => {
  it('offers a delivery the line offers to a receiver', () => {
    expect(orderItemActionGates.deliver(line(['deliver']), RECEIVER)).toBe(true)
  })

  it('does not offer a delivery the line does not offer', () => {
    expect(orderItemActionGates.deliver(line(['cancel']), RECEIVER)).toBe(false)
  })

  it('still requires receive:deliveries', () => {
    expect(orderItemActionGates.deliver(line(['deliver']), ORDER_MANAGER)).toBe(false)
  })
})
