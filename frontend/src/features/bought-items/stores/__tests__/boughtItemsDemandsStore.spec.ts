import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type {
  DemandItemCreateRequest,
  DemandItemFilterParams,
  DemandItemUpdateRequest,
} from '../../types/boughtItemsDemandsRequest'
import type { BoughtItemDemandResponse, BoughtItemDemandStatus } from '../../types/boughtItemsDemandsResponse'

const createMock = vi.fn<(payload: DemandItemCreateRequest) => Promise<BoughtItemDemandResponse>>()
const getMock =
  vi.fn<(params?: DemandItemFilterParams) => Promise<PageResponse<BoughtItemDemandResponse>>>()
const updateMock =
  vi.fn<(id: number, payload: DemandItemUpdateRequest) => Promise<BoughtItemDemandResponse>>()
const updateStatusMock = vi.fn<(id: number, newStatus: BoughtItemDemandStatus) => Promise<BoughtItemDemandResponse>>()
const deleteMock = vi.fn<(id: number) => Promise<BoughtItemDemandResponse>>()
const setBucketMock = vi.fn<(id: number, bucketId: number | null) => Promise<BoughtItemDemandResponse>>()

vi.mock('../../api/boughtItemDemandsApi', () => ({
  createDemand: (payload: DemandItemCreateRequest) => createMock(payload),
  getDemands: (params?: DemandItemFilterParams) => getMock(params),
  updateDemand: (id: number, payload: DemandItemUpdateRequest) => updateMock(id, payload),
  updateDemandStatus: (id: number, newStatus: BoughtItemDemandStatus) => updateStatusMock(id, newStatus),
  setDemandBucket: (id: number, bucketId: number | null) => setBucketMock(id, bucketId),
}))
vi.mock('../../api/deleteBoughtItemDemand', () => ({
  deleteBoughtItemDemand: (id: number) => deleteMock(id),
}))

import { useBoughtItemsDemandsStore } from '../boughtItemsDemandsStore'

function makeDemand(overrides: Partial<BoughtItemDemandResponse> = {}): BoughtItemDemandResponse {
  return { id: 1, quantity: 10, status: 'open', ...overrides } as unknown as BoughtItemDemandResponse
}

function page(items: BoughtItemDemandResponse[], total = items.length): PageResponse<BoughtItemDemandResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('useBoughtItemsDemandsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    createMock.mockReset()
    getMock.mockReset()
    updateMock.mockReset()
    updateStatusMock.mockReset()
    deleteMock.mockReset()
    setBucketMock.mockReset()
  })

  it('starts with no items, loading off, and refreshTrigger at zero', () => {
    const store = useBoughtItemsDemandsStore()
    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
    expect(store.loading).toBe(false)
    expect(store.refreshTrigger).toBe(0)
  })

  it('refresh marks loading synchronously and populates items/total from the envelope', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1 }), makeDemand({ id: 2 })], 2))
    const store = useBoughtItemsDemandsStore()

    const promise = store.refresh({ item_id: 7 })
    expect(store.loading).toBe(true)
    await promise

    expect(getMock).toHaveBeenCalledWith({ item_id: 7 })
    expect(store.loading).toBe(false)
    expect(store.items).toHaveLength(2)
    expect(store.total).toBe(2)
  })

  it('a failed refresh surfaces through error without throwing, leaving items untouched', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1 })], 1))
    const store = useBoughtItemsDemandsStore()
    await store.refresh()

    getMock.mockRejectedValueOnce(new Error('network error'))

    await store.refresh()
    expect(store.loading).toBe(false)
    expect(store.items).toHaveLength(1)
  })

  it('triggerRefresh bumps refreshTrigger', () => {
    const store = useBoughtItemsDemandsStore()
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(1)
  })

  it('clear resets items and total', async () => {
    getMock.mockResolvedValue(page([makeDemand()], 1))
    const store = useBoughtItemsDemandsStore()
    await store.refresh()

    store.clear()

    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
  })

  it('create delegates to the API and returns its result without touching local state', async () => {
    const created = makeDemand({ id: 42 })
    createMock.mockResolvedValue(created)
    const store = useBoughtItemsDemandsStore()

    const payload: DemandItemCreateRequest = { item_id: 1, project_id: 1, quantity: 5, unit: 'pcs' }
    const result = await store.create(payload)

    expect(createMock).toHaveBeenCalledWith(payload)
    expect(result).toBe(created)
    expect(store.items).toEqual([])
  })

  it('create propagates a rejection from the API', async () => {
    createMock.mockRejectedValue(new Error('validation failed'))
    const store = useBoughtItemsDemandsStore()

    await expect(
      store.create({ item_id: 1, project_id: 1, quantity: 5, unit: 'pcs' }),
    ).rejects.toThrow('validation failed')
  })

  it('update replaces the matching item in place and returns the updated demand', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1, quantity: 5 })], 1))
    const store = useBoughtItemsDemandsStore()
    await store.refresh()
    const updated = makeDemand({ id: 1, quantity: 8 })
    updateMock.mockResolvedValue(updated)

    const payload: DemandItemUpdateRequest = { quantity: 8, unit: 'pcs' }
    const result = await store.update(1, payload)

    expect(updateMock).toHaveBeenCalledWith(1, payload)
    expect(result).toBe(updated)
    expect(store.items[0]).toEqual(updated)
  })

  it('update propagates a rejection from the API', async () => {
    updateMock.mockRejectedValue(new Error('conflict'))
    const store = useBoughtItemsDemandsStore()

    await expect(store.update(1, { quantity: 1, unit: 'pcs' })).rejects.toThrow('conflict')
  })

  it('updateStatus replaces the matching item in place', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1, status: 'open' })], 1))
    const store = useBoughtItemsDemandsStore()
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
    const store = useBoughtItemsDemandsStore()

    await expect(store.updateStatus(1, 'canceled')).rejects.toThrow('invalid transition')
  })

  it('setBucket replaces the matching item in place with the new bucket_id', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1, bucket_id: null } as never)], 1))
    const store = useBoughtItemsDemandsStore()
    await store.refresh()
    const updated = makeDemand({ id: 1, bucket_id: 3 } as never)
    setBucketMock.mockResolvedValue(updated)

    const result = await store.setBucket(1, 3)

    expect(setBucketMock).toHaveBeenCalledWith(1, 3)
    expect(result).toBe(updated)
    expect(store.items[0]).toEqual(updated)
  })

  it('setBucket propagates a rejection from the API', async () => {
    setBucketMock.mockRejectedValue(new Error('bucket not found'))
    const store = useBoughtItemsDemandsStore()

    await expect(store.setBucket(1, 3)).rejects.toThrow('bucket not found')
  })

  it('remove deletes via the API and drops the item from local state, clamping total at zero', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1 })], 1))
    const store = useBoughtItemsDemandsStore()
    await store.refresh()
    deleteMock.mockResolvedValue(makeDemand({ id: 1 }))

    await store.remove(1)

    expect(deleteMock).toHaveBeenCalledWith(1)
    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
  })

  it('remove is a no-op on local state when the id is not in the cached list', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1 })], 1))
    const store = useBoughtItemsDemandsStore()
    await store.refresh()
    deleteMock.mockResolvedValue(makeDemand({ id: 999 }))

    await store.remove(999)

    expect(store.items.map((item) => item.id)).toEqual([1])
    // total still drops, since remove doesn't check whether the id was cached.
    expect(store.total).toBe(0)
  })

  it('remove propagates a rejection from the API and leaves local state untouched', async () => {
    getMock.mockResolvedValue(page([makeDemand({ id: 1 })], 1))
    const store = useBoughtItemsDemandsStore()
    await store.refresh()
    deleteMock.mockRejectedValue(new Error('in use'))

    await expect(store.remove(1)).rejects.toThrow('in use')
    expect(store.items).toHaveLength(1)
    expect(store.total).toBe(1)
  })

  it('replaceItem is a no-op when the id is not present in the cached list', () => {
    const store = useBoughtItemsDemandsStore()
    store.items = [makeDemand({ id: 1 })]

    store.replaceItem(makeDemand({ id: 999 }))

    expect(store.items.map((item) => item.id)).toEqual([1])
  })
})
