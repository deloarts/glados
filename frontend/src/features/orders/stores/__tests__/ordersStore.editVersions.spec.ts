import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { makeOrderItemResponse, makeOrderResponse } from '@/test-utils/factories'

const cancelOrderMock = vi.fn<(id: number, version: number) => Promise<unknown>>()
const cancelOrderItemMock =
  vi.fn<(orderId: number, itemId: number, version: number) => Promise<unknown>>()
const reopenOrderItemMock =
  vi.fn<(orderId: number, itemId: number, version: number) => Promise<unknown>>()
const getOrderMock = vi.fn<(id: number) => Promise<unknown>>()

vi.mock('../../api/cancelOrder', () => ({
  cancelOrder: (id: number, version: number) => cancelOrderMock(id, version),
}))
vi.mock('../../api/cancelOrderItem', () => ({
  cancelOrderItem: (orderId: number, itemId: number, version: number) =>
    cancelOrderItemMock(orderId, itemId, version),
}))
vi.mock('../../api/reopenOrderItem', () => ({
  reopenOrderItem: (orderId: number, itemId: number, version: number) =>
    reopenOrderItemMock(orderId, itemId, version),
}))
vi.mock('../../api/getOrder', () => ({ getOrder: (id: number) => getOrderMock(id) }))

import { useOrdersStore } from '../ordersStore'

// The store sends the edit version its caller showed, so a concurrent
// change answers 409, even for an order or a line the store does not hold.
describe('ordersStore edit versions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    cancelOrderMock.mockReset().mockResolvedValue({})
    cancelOrderItemMock.mockReset().mockResolvedValue({})
    reopenOrderItemMock.mockReset().mockResolvedValue({})
  })

  it('cancels an order with the edit version the caller showed', async () => {
    const order = makeOrderResponse({ id: 3, edit_version: 4 })
    getOrderMock.mockResolvedValue(order)
    const store = useOrdersStore()
    store.items = [order]

    await store.cancel(3, order.edit_version)

    expect(cancelOrderMock).toHaveBeenCalledWith(3, 4)
  })

  it('cancels a line with the line edit version the caller showed', async () => {
    const line = makeOrderItemResponse({ id: 9, order_id: 3, edit_version: 2 })
    const order = makeOrderResponse({ id: 3, items: [line] })
    getOrderMock.mockResolvedValue(order)
    const store = useOrdersStore()
    store.items = [order]

    await store.cancelItem(3, 9, line.edit_version)

    expect(cancelOrderItemMock).toHaveBeenCalledWith(3, 9, 2)
  })

  it('sends the version for an order it does not hold', async () => {
    getOrderMock.mockResolvedValue(makeOrderResponse({ id: 5 }))
    const store = useOrdersStore()

    await store.cancel(5, 7)

    expect(cancelOrderMock).toHaveBeenCalledWith(5, 7)
  })

  it('reopens a line with the line edit version the caller showed', async () => {
    const line = makeOrderItemResponse({ id: 9, order_id: 3, edit_version: 5 })
    getOrderMock.mockResolvedValue(makeOrderResponse({ id: 3, items: [line] }))
    const store = useOrdersStore()

    await store.reopenItem(3, 9, line.edit_version)

    expect(reopenOrderItemMock).toHaveBeenCalledWith(3, 9, 5)
  })
})
