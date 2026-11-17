import { describe, it, expect, vi } from 'vitest'

const get = vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => get(url, config),
  },
}))

import { getSupplierDraftOrders } from '../api/getSupplierDraftOrders'

describe('getSupplierDraftOrders', () => {
  it('asks for the drafts and partially ordered orders of the supplier and leaves out canceled ones', async () => {
    get.mockResolvedValue({
      data: {
        items: [
          { id: 1, order_number: 'BN-1', canceled_at: null },
          { id: 2, order_number: 'BN-2', canceled_at: '2026-10-31T10:00:00Z' },
        ],
        total: 2,
        limit: 200,
        skip: 0,
      },
    })

    const orders = await getSupplierDraftOrders(7)

    expect(get).toHaveBeenCalledOnce()
    expect(get.mock.calls[0]?.[1]?.params).toMatchObject({
      supplier_id: 7,
      status: ['draft', 'partially_ordered'],
    })
    expect(orders).toEqual([{ id: 1, order_number: 'BN-1' }])
  })
})
