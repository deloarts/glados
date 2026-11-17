import { describe, it, expect, vi, beforeEach } from 'vitest'

const postMock = vi.fn<(url: string, payload?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: { post: (url: string, payload?: unknown) => postMock(url, payload) },
}))

import { createOrder } from '../createOrder'
import type { OrderCreateRequest } from '../../types/ordersRequest'
import type { OrderResponse } from '../../types/ordersResponse'

describe('createOrder', () => {
  beforeEach(() => {
    postMock.mockReset()
  })

  it('POSTs the payload to /orders and returns the created order', async () => {
    const payload: OrderCreateRequest = { supplier_id: 7, note: 'Rush' }
    const created = { id: 9, order_number: 'ORD-9' } as OrderResponse
    postMock.mockResolvedValue({ data: created })

    const result = await createOrder(payload)

    expect(postMock).toHaveBeenCalledWith('/orders/', payload)
    expect(result).toBe(created)
  })

  it('propagates a failed request instead of swallowing it', async () => {
    const error = new Error('network down')
    postMock.mockRejectedValue(error)

    await expect(createOrder({ supplier_id: 1 })).rejects.toBe(error)
  })
})
