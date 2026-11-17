import { describe, it, expect, vi, beforeEach } from 'vitest'

const putMock = vi.fn<(url: string, payload?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: { put: (url: string, payload?: unknown) => putMock(url, payload) },
}))

import { updateOrder } from '../updateOrder'
import type { OrderUpdateRequest } from '../../types/ordersRequest'
import type { OrderResponse } from '../../types/ordersResponse'

describe('updateOrder', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('PUTs the payload to /orders/{id} and returns the updated order', async () => {
    const payload: OrderUpdateRequest = {
      note: 'Updated note',
      supplier_id: 3,
      expected_edit_version: 2,
    }
    const updated = { id: 42, order_number: 'ORD-42' } as OrderResponse
    putMock.mockResolvedValue({ data: updated })

    const result = await updateOrder(42, payload)

    expect(putMock).toHaveBeenCalledWith('/orders/42', payload)
    expect(result).toBe(updated)
  })

  it('propagates a failed request instead of swallowing it', async () => {
    const error = new Error('422 validation')
    putMock.mockRejectedValue(error)

    await expect(updateOrder(1, { expected_edit_version: 0 })).rejects.toBe(error)
  })
})
