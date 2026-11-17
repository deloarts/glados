import { describe, it, expect, vi, beforeEach } from 'vitest'

const putMock = vi.fn<(url: string, body?: unknown, config?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    put: (url: string, body?: unknown, config?: unknown) => putMock(url, body, config),
  },
}))

import { cancelOrder } from '../cancelOrder'
import type { OrderResponse } from '../../types/ordersResponse'

describe('cancelOrder', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('PUTs to /orders/{id}/cancel with the edit version and returns the cancelled order', async () => {
    const cancelled = { id: 5, status: 'cancelled' } as unknown as OrderResponse
    putMock.mockResolvedValue({ data: cancelled })

    const result = await cancelOrder(5, 3)

    expect(putMock).toHaveBeenCalledWith('/orders/5/cancel', undefined, {
      params: { expected_edit_version: 3 },
    })
    expect(result).toBe(cancelled)
  })

  it('propagates a failed request instead of swallowing it', async () => {
    const error = new Error('409 conflict')
    putMock.mockRejectedValue(error)

    await expect(cancelOrder(5, 0)).rejects.toBe(error)
  })
})
