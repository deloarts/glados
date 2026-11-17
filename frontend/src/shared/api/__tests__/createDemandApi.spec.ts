import { describe, it, expect, vi, beforeEach } from 'vitest'

const calls: { method: string; args: unknown[] }[] = []

function record(method: string) {
  return (...args: unknown[]) => {
    calls.push({ method, args })
    return Promise.resolve({ data: { ok: true } })
  }
}

vi.mock('@/core/api', () => ({
  default: {
    get: record('get'),
    post: record('post'),
    put: record('put'),
    patch: record('patch'),
    delete: record('delete'),
  },
}))

import {
  createDemandApi,
  createDemandBatchApi,
  createOrderItemAllocationApi,
  type DemandApiTypes,
  type DemandKind,
} from '../createDemandApi'
import { createFilesApi } from '../createFilesApi'

// Every call carries a fresh Idempotency-Key (core/api/idempotency.ts).
const withKey = { headers: { 'Idempotency-Key': expect.any(String) } }

const ROUTES: Record<DemandKind, { demands: string; allocations: string }> = {
  bought: { demands: '/bought-items-demands', allocations: '/bought-items-allocations' },
  made: { demands: '/made-items-demands', allocations: '/made-items-allocations' },
  source: { demands: '/source-item-demands', allocations: '/source-item-allocations' },
}

describe('createDemandApi', () => {
  beforeEach(() => {
    calls.length = 0
  })

  describe.each(Object.keys(ROUTES) as DemandKind[])('%s', (kind) => {
    const { demands, allocations } = ROUTES[kind]
    const api = createDemandApi<DemandApiTypes>(kind)

    it('sends every shared demand and allocation route unchanged', async () => {
      await api.list({ skip: 0 })
      await api.list()
      await api.create({ quantity: 1 })
      await api.update(3, { quantity: 2 })
      await api.setBucket(3, null)
      await api.updateStatus(3, 'canceled')
      await api.getAllocations(4)
      await api.getSummaryBatch([1, 2])
      await api.fulfillFromStock(4, 5)
      await api.updateStockAllocation(4, 6)
      await api.deleteStockAllocation(4)

      expect(calls).toEqual([
        { method: 'get', args: [demands, { params: { skip: 0 } }] },
        { method: 'get', args: [demands] },
        { method: 'post', args: [demands, { quantity: 1 }] },
        { method: 'put', args: [`${demands}/3`, { quantity: 2 }] },
        { method: 'put', args: [`${demands}/3/bucket`, { bucket_id: null }] },
        {
          method: 'put',
          args: [`${demands}/3/status`, null, { params: { new_status: 'canceled' } }],
        },
        { method: 'get', args: [`${allocations}/demand/4`] },
        { method: 'post', args: [`${allocations}/demands/summary-batch`, [1, 2]] },
        { method: 'post', args: [`${allocations}/demand/4/fulfill-from-stock`, { quantity: 5 }, withKey] },
        { method: 'put', args: [`${allocations}/demand/4/stock`, { quantity: 6 }] },
        { method: 'delete', args: [`${allocations}/demand/4/stock`] },
      ])
    })

    it('resolves to the response body', async () => {
      await expect(api.setBucket(1, 2)).resolves.toEqual({ ok: true })
    })

    it('cancels through the cancel route without a body', async () => {
      await expect(api.cancel(5)).resolves.toEqual({ ok: true })

      expect(calls).toEqual([{ method: 'post', args: [`${demands}/5/cancel`, null] }])
    })
  })

  it('batch import posts to the kind prefix', async () => {
    const api = createDemandBatchApi<{
      validateRequest: { rows: [] }
      validateResponse: unknown
      commitRequest: { rows: [] }
      commitResponse: unknown
    }>('made')
    await api.validateBatch({ rows: [] })
    await api.commitBatch({ rows: [] })

    expect(calls).toEqual([
      { method: 'post', args: ['/made-items-demands/batch/validate', { rows: [] }] },
      { method: 'post', args: ['/made-items-demands/batch/commit', { rows: [] }, withKey] },
    ])
  })

  it('order-item allocations keep the trailing slash on create', async () => {
    const api = createOrderItemAllocationApi<{
      allocation: unknown
      createRequest: { quantity: number }
      autoAllocateResult: unknown
    }>('source')
    await api.create({ quantity: 1 })
    await api.update(2, 3, 4)
    await api.remove(2, 3)
    await api.autoAllocate(2)

    expect(calls).toEqual([
      { method: 'post', args: ['/source-item-allocations/', { quantity: 1 }, withKey] },
      { method: 'put', args: ['/source-item-allocations/demand/2/order-item/3', { quantity: 4 }] },
      { method: 'delete', args: ['/source-item-allocations/demand/2/order-item/3'] },
      { method: 'post', args: ['/source-item-allocations/demand/2/auto-allocate', undefined] },
    ])
  })
})

describe('createFilesApi', () => {
  beforeEach(() => {
    calls.length = 0
  })

  it('maps the file routes and skips the batch request for no items', async () => {
    const api = createFilesApi<{ file: unknown; category: string }>('bought')
    const file = new File(['x'], 'a.txt')

    await expect(api.listForItems([])).resolves.toEqual([])
    await api.listForItems([1, 2])
    await api.list(7)
    await api.upload(7, file, 'image')
    await api.remove(7, 8)
    await api.getBlob(7, 8)

    expect(calls.map((c) => [c.method, c.args[0]])).toEqual([
      ['get', '/bought-items-files'],
      ['get', '/bought-items/7/files'],
      ['post', '/bought-items/7/files'],
      ['delete', '/bought-items/7/files/8'],
      ['get', '/bought-items/7/files/8'],
    ])
    expect(calls[0]!.args[1]).toEqual({ params: { item_ids: [1, 2] } })
    const [, formData, config] = calls[2]!.args as [string, FormData, unknown]
    expect(formData.get('category')).toBe('image')
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
    expect(calls[4]!.args[1]).toEqual({ responseType: 'blob' })
  })
})
