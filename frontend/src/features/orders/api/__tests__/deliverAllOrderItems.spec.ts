import { describe, it, expect, vi, beforeEach } from 'vitest'

const putMock =
  vi.fn<(url: string, body: unknown, config?: { params?: Record<string, unknown> }) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    put: (url: string, body: unknown, config?: { params?: Record<string, unknown> }) =>
      putMock(url, body, config),
  },
}))

import { deliverAllOrderItems } from '../deliverAllOrderItems'
import type { OrderItemRejectionRequest } from '../../types/ordersRequest'
import type { OrderItemResponse } from '../../types/ordersResponse'

// Every call carries a fresh Idempotency-Key (core/api/idempotency.ts).
const withKey = { headers: { 'Idempotency-Key': expect.any(String) } }

describe('deliverAllOrderItems', () => {
  beforeEach(() => {
    putMock.mockReset()
    putMock.mockResolvedValue({ data: [] as OrderItemResponse[] })
  })

  it('sends a null body and no params when neither storagePlace nor rejections is given', async () => {
    await deliverAllOrderItems(7)

    expect(putMock).toHaveBeenCalledWith('/orders/7/deliver-all-items', null, withKey)
  })

  it('includes the storage_place param when given, still with a null body', async () => {
    await deliverAllOrderItems(7, 'Shelf B2')

    expect(putMock).toHaveBeenCalledWith('/orders/7/deliver-all-items', null, {
      ...withKey,
      params: { storage_place: 'Shelf B2' },
    })
  })

  it('sends a null body when rejections is an empty array (existing behaviour stays unchanged)', async () => {
    await deliverAllOrderItems(7, undefined, [])

    expect(putMock).toHaveBeenCalledWith('/orders/7/deliver-all-items', null, withKey)
  })

  it('wraps a non-empty rejections list in the request body', async () => {
    const rejections: OrderItemRejectionRequest[] = [
      {
        order_item_id: 3,
        quantity_rejected: 1,
        rejection_reason: 'supplier_damage',
        rejection_outcome: 'lost',
        create_replacement: true,
      },
    ]

    await deliverAllOrderItems(7, 'Shelf B2', rejections)

    expect(putMock).toHaveBeenCalledWith(
      '/orders/7/deliver-all-items',
      { rejections },
      { ...withKey, params: { storage_place: 'Shelf B2' } },
    )
  })

  it('returns the response data', async () => {
    const delivered = [{ id: 3, status: 'delivered' }] as unknown as OrderItemResponse[]
    putMock.mockResolvedValue({ data: delivered })

    const result = await deliverAllOrderItems(7)

    expect(result).toBe(delivered)
  })
})
