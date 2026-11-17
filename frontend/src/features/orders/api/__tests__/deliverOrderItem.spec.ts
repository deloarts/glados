import { describe, it, expect, vi, beforeEach } from 'vitest'

const putMock =
  vi.fn<(url: string, body: unknown, config?: { params?: Record<string, unknown> }) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    put: (url: string, body: unknown, config?: { params?: Record<string, unknown> }) =>
      putMock(url, body, config),
  },
}))

import { deliverOrderItem } from '../deliverOrderItem'
import type { OrderItemResponse } from '../../types/ordersResponse'

// Every call carries a fresh Idempotency-Key (core/api/idempotency.ts).
const withKey = { headers: { 'Idempotency-Key': expect.any(String) } }

describe('deliverOrderItem', () => {
  beforeEach(() => {
    putMock.mockReset()
    putMock.mockResolvedValue({ data: {} as OrderItemResponse })
  })

  it('sends no params object at all when neither quantity nor storagePlace is given', async () => {
    await deliverOrderItem(11)

    expect(putMock).toHaveBeenCalledWith(
      '/bought-items-allocations/order-item/11/deliver',
      null,
      withKey,
    )
  })

  it('includes quantity alone when only quantity is provided', async () => {
    await deliverOrderItem(11, 5)

    expect(putMock).toHaveBeenCalledWith(
      '/bought-items-allocations/order-item/11/deliver',
      null,
      { ...withKey, params: { quantity: 5 } },
    )
  })

  it('includes both quantity and storage_place when both are given', async () => {
    await deliverOrderItem(11, 5, 'Shelf A1')

    expect(putMock).toHaveBeenCalledWith(
      '/bought-items-allocations/order-item/11/deliver',
      null,
      { ...withKey, params: { quantity: 5, storage_place: 'Shelf A1' } },
    )
  })

  it('treats an empty storagePlace string as absent (falsy check, not a real value)', async () => {
    await deliverOrderItem(11, undefined, '')

    // Documents current behaviour: `if (storagePlace)` drops an explicit ''
    // just like an omitted argument would, so no params object is sent.
    expect(putMock).toHaveBeenCalledWith(
      '/bought-items-allocations/order-item/11/deliver',
      null,
      withKey,
    )
  })

  it('returns the response data', async () => {
    const delivered = { id: 11, status: 'delivered' } as unknown as OrderItemResponse
    putMock.mockResolvedValue({ data: delivered })

    const result = await deliverOrderItem(11, 5)

    expect(result).toBe(delivered)
  })
})
