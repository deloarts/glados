import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type {
  SourceItemDemandCreateRequest,
  SourceItemDemandFilterParams,
  SourceItemDemandUpdateRequest,
} from '../../types/sourceItemDemandsRequest'
import type {
  SourceItemDemandResponse,
  SourceItemDemandStatus,
} from '../../types/sourceItemDemandsResponse'

const createMock = vi.fn<(payload: SourceItemDemandCreateRequest) => Promise<SourceItemDemandResponse>>()
const getMock =
  vi.fn<
    (params?: SourceItemDemandFilterParams) => Promise<PageResponse<SourceItemDemandResponse>>
  >()
const updateMock =
  vi.fn<
    (id: number, payload: SourceItemDemandUpdateRequest) => Promise<SourceItemDemandResponse>
  >()
const updateStatusMock =
  vi.fn<(id: number, newStatus: SourceItemDemandStatus) => Promise<SourceItemDemandResponse>>()
const cancelMock =
  vi.fn<(demandId: number, cancelLot: boolean) => Promise<SourceItemDemandResponse>>()
const cancelByStatusMock =
  vi.fn<(demandId: number, cancelLot: boolean) => Promise<SourceItemDemandResponse>>()
const setBucketMock =
  vi.fn<(id: number, bucketId: number | null) => Promise<SourceItemDemandResponse>>()

vi.mock('../../api/sourceItemDemandsApi', () => ({
  createSourceItemDemand: (payload: SourceItemDemandCreateRequest) => createMock(payload),
  getSourceItemDemands: (params?: SourceItemDemandFilterParams) => getMock(params),
  updateSourceItemDemand: (id: number, payload: SourceItemDemandUpdateRequest) =>
    updateMock(id, payload),
  updateSourceItemDemandStatus: (id: number, newStatus: SourceItemDemandStatus) =>
    updateStatusMock(id, newStatus),
  setSourceItemDemandBucket: (id: number, bucketId: number | null) =>
    setBucketMock(id, bucketId),
}))
vi.mock('../../api/cancelSourceItemDemand', () => ({
  cancelSourceItemDemand: (demandId: number, cancelLot: boolean) => cancelMock(demandId, cancelLot),
  cancelSourceItemDemandByStatus: (demandId: number, cancelLot: boolean) =>
    cancelByStatusMock(demandId, cancelLot),
}))

import { useSourceItemDemandsStore } from '../sourceItemDemandsStore'

function makeDemand(overrides: Partial<SourceItemDemandResponse> = {}): SourceItemDemandResponse {
  return { id: 1, quantity: 10, status: 'open', ...overrides } as unknown as SourceItemDemandResponse
}

function page(
  items: SourceItemDemandResponse[],
  total = items.length,
): PageResponse<SourceItemDemandResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('useSourceItemDemandsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    createMock.mockReset()
    getMock.mockReset()
    updateMock.mockReset()
    updateStatusMock.mockReset()
    cancelMock.mockReset()
    setBucketMock.mockReset()
  })

  it('starts with no items, loading off, and refreshTrigger at zero', () => {
    const store = useSourceItemDemandsStore()
    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
    expect(store.loading).toBe(false)
    expect(store.refreshTrigger).toBe(0)
  })

  it('refresh marks loading synchronously and populates items/total from the envelope', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1 }), makeDemand({ id: 2 })], 2))
    const store = useSourceItemDemandsStore()

    const promise = store.refresh({ lot_id: [1] })
    expect(store.loading).toBe(true)
    await promise

    expect(getMock).toHaveBeenCalledWith({ lot_id: [1] })
    expect(store.loading).toBe(false)
    expect(store.items).toHaveLength(2)
    expect(store.total).toBe(2)
  })

  it('refresh with no params calls the API with undefined', async () => {
    getMock.mockResolvedValue(page([]))
    const store = useSourceItemDemandsStore()

    await store.refresh()

    expect(getMock).toHaveBeenCalledWith(undefined)
  })

  it('a failed refresh surfaces through error without throwing, leaving items untouched', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1 })], 1))
    const store = useSourceItemDemandsStore()
    await store.refresh()

    getMock.mockRejectedValueOnce(new Error('network error'))

    await store.refresh()
    expect(store.loading).toBe(false)
    // refresh never cleared items before the request failed.
    expect(store.items).toHaveLength(1)
  })

  it('triggerRefresh bumps refreshTrigger', () => {
    const store = useSourceItemDemandsStore()
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(2)
  })

  it('clear resets items and total', async () => {
    getMock.mockResolvedValue(page([makeDemand()], 1))
    const store = useSourceItemDemandsStore()
    await store.refresh()

    store.clear()

    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
  })

  it('create delegates to the API and returns its result without touching local state', async () => {
    const created = makeDemand({ id: 42 })
    createMock.mockResolvedValue(created)
    const store = useSourceItemDemandsStore()

    const payload: SourceItemDemandCreateRequest = { lot_id: 1, quantity: 5 }
    const result = await store.create(payload)

    expect(createMock).toHaveBeenCalledWith(payload)
    expect(result).toBe(created)
    expect(store.items).toEqual([])
  })

  it('create propagates a rejection from the API', async () => {
    createMock.mockRejectedValue(new Error('validation failed'))
    const store = useSourceItemDemandsStore()

    await expect(store.create({ lot_id: 1, quantity: 5 })).rejects.toThrow('validation failed')
  })

  it('update replaces the matching item in place and returns the updated demand', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1, quantity: 5 })], 1))
    const store = useSourceItemDemandsStore()
    await store.refresh()
    const updated = makeDemand({ id: 1, quantity: 8 })
    updateMock.mockResolvedValue(updated)

    const payload: SourceItemDemandUpdateRequest = { quantity: 8, unit: 'pcs' }
    const result = await store.update(1, payload)

    expect(updateMock).toHaveBeenCalledWith(1, payload)
    expect(result).toBe(updated)
    expect(store.items[0]).toEqual(updated)
  })

  it('update is a no-op on local state when the id is not in the cached list', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1 })], 1))
    const store = useSourceItemDemandsStore()
    await store.refresh()
    updateMock.mockResolvedValue(makeDemand({ id: 999 }))

    await store.update(999, { quantity: 1, unit: 'pcs' })

    expect(store.items.map((item) => item.id)).toEqual([1])
  })

  it('update propagates a rejection from the API', async () => {
    updateMock.mockRejectedValue(new Error('conflict'))
    const store = useSourceItemDemandsStore()

    await expect(store.update(1, { quantity: 1, unit: 'pcs' })).rejects.toThrow('conflict')
  })

  it('updateStatus replaces the matching item in place', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1, status: 'open' })], 1))
    const store = useSourceItemDemandsStore()
    await store.refresh()
    const updated = makeDemand({ id: 1, status: 'fulfilled' })
    updateStatusMock.mockResolvedValue(updated)

    const result = await store.updateStatus(1, 'fulfilled')

    expect(updateStatusMock).toHaveBeenCalledWith(1, 'fulfilled')
    expect(result).toBe(updated)
    expect(store.items[0]).toEqual(updated)
  })

  it('updateStatus propagates a rejection from the API', async () => {
    updateStatusMock.mockRejectedValue(new Error('invalid transition'))
    const store = useSourceItemDemandsStore()

    await expect(store.updateStatus(1, 'canceled')).rejects.toThrow('invalid transition')
  })

  it('cancel replaces the matching item in place with the canceled demand', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1, status: 'open' })], 1))
    const store = useSourceItemDemandsStore()
    await store.refresh()
    const canceled = makeDemand({ id: 1, status: 'canceled' })
    cancelMock.mockResolvedValue(canceled)

    const result = await store.cancel(1, true)

    expect(cancelMock).toHaveBeenCalledWith(1, true)
    expect(result).toBe(canceled)
    expect(store.items[0]).toEqual(canceled)
  })

  it('cancelByStatus passes the lot choice and replaces the item in place', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1, status: 'open' })], 1))
    const store = useSourceItemDemandsStore()
    await store.refresh()
    const canceled = makeDemand({ id: 1, status: 'canceled' })
    cancelByStatusMock.mockResolvedValue(canceled)

    await store.cancelByStatus(1, false)

    expect(cancelByStatusMock).toHaveBeenCalledWith(1, false)
    expect(store.items[0]).toEqual(canceled)
  })

  it('cancel propagates a rejection from the API', async () => {
    cancelMock.mockRejectedValue(new Error('already fulfilled'))
    const store = useSourceItemDemandsStore()

    await expect(store.cancel(1, false)).rejects.toThrow('already fulfilled')
  })

  it('setBucket replaces the matching item in place with the new bucket_id', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1, bucket_id: null } as never)], 1))
    const store = useSourceItemDemandsStore()
    await store.refresh()
    const updated = makeDemand({ id: 1, bucket_id: 3 } as never)
    setBucketMock.mockResolvedValue(updated)

    const result = await store.setBucket(1, 3)

    expect(setBucketMock).toHaveBeenCalledWith(1, 3)
    expect(result).toBe(updated)
    expect(store.items[0]).toEqual(updated)
  })

  it('setBucket accepts null to unassign the bucket', async () => {
    const updated = makeDemand({ id: 1, bucket_id: null } as never)
    setBucketMock.mockResolvedValue(updated)
    const store = useSourceItemDemandsStore()

    await store.setBucket(1, null)

    expect(setBucketMock).toHaveBeenCalledWith(1, null)
  })

  it('setBucket propagates a rejection from the API', async () => {
    setBucketMock.mockRejectedValue(new Error('bucket not found'))
    const store = useSourceItemDemandsStore()

    await expect(store.setBucket(1, 3)).rejects.toThrow('bucket not found')
  })

  it('replaceItem is a no-op when the id is not present in the cached list', () => {
    const store = useSourceItemDemandsStore()
    store.items = [makeDemand({ id: 1 })]

    store.replaceItem(makeDemand({ id: 999 }))

    expect(store.items.map((item) => item.id)).toEqual([1])
  })
})
