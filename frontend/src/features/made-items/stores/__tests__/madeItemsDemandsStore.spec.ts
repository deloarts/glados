import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type {
  MadeItemDemandCreateRequest,
  MadeItemDemandFilterParams,
  MadeItemDemandUpdateRequest,
} from '../../types/madeItemsDemandsRequest'
import type {
  MadeItemDemandCancelImpact,
  MadeItemDemandResponse,
  MadeItemDemandStatus,
} from '../../types/madeItemsDemandsResponse'

const createMock = vi.fn<(payload: MadeItemDemandCreateRequest) => Promise<MadeItemDemandResponse>>()
const getDemandsMock =
  vi.fn<(params?: MadeItemDemandFilterParams) => Promise<PageResponse<MadeItemDemandResponse>>>()
const updateMock =
  vi.fn<(id: number, payload: MadeItemDemandUpdateRequest) => Promise<MadeItemDemandResponse>>()
const updateStatusMock =
  vi.fn<(id: number, newStatus: MadeItemDemandStatus) => Promise<MadeItemDemandResponse>>()
const deleteMock = vi.fn<(id: number) => Promise<MadeItemDemandResponse>>()
const cancelImpactMock = vi.fn<(id: number) => Promise<MadeItemDemandCancelImpact>>()
const setBucketMock =
  vi.fn<(id: number, bucketId: number | null) => Promise<MadeItemDemandResponse>>()

vi.mock('../../api/madeItemDemandsApi', () => ({
  createMadeItemDemand: (payload: MadeItemDemandCreateRequest) => createMock(payload),
  getMadeItemDemands: (params?: MadeItemDemandFilterParams) => getDemandsMock(params),
  updateMadeItemDemand: (id: number, payload: MadeItemDemandUpdateRequest) => updateMock(id, payload),
  updateMadeItemDemandStatus: (id: number, newStatus: MadeItemDemandStatus) =>
    updateStatusMock(id, newStatus),
  setMadeItemDemandBucket: (id: number, bucketId: number | null) => setBucketMock(id, bucketId),
}))
vi.mock('../../api/deleteMadeItemDemand', () => ({
  deleteMadeItemDemand: (id: number) => deleteMock(id),
}))
vi.mock('../../api/getMadeItemDemandCancelImpact', () => ({
  getMadeItemDemandCancelImpact: (id: number) => cancelImpactMock(id),
}))

import { useMadeItemsDemandsStore } from '../madeItemsDemandsStore'
import { makeMadeItemDemandResponse } from '@/test-utils/factories'

// Mirrors the fixture used by MadeItemsDemandsManageLots.spec.ts, kept as
// its own local copy since specs don't import from one another.
function makeImpact(overrides: Partial<MadeItemDemandCancelImpact> = {}): MadeItemDemandCancelImpact {
  return {
    demand_item_id: 1,
    status: 'ordered',
    quantity: 5,
    unit: 'PCS',
    item_part_number: 'PN-1',
    item_revision: 'A',
    item_article_name: 'Bracket',
    project_number: 'P-001',
    can_cancel_lots: true,
    lots: [],
    ...overrides,
  }
}

function page(
  items: MadeItemDemandResponse[],
  total = items.length,
): PageResponse<MadeItemDemandResponse> {
  return { items, total, limit: 25, skip: 0 }
}

describe('useMadeItemsDemandsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    createMock.mockReset()
    getDemandsMock.mockReset()
    updateMock.mockReset()
    updateStatusMock.mockReset()
    deleteMock.mockReset()
    cancelImpactMock.mockReset()
    setBucketMock.mockReset()
  })

  it('starts empty with loading false and refreshTrigger at 0', () => {
    const store = useMadeItemsDemandsStore()
    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
    expect(store.loading).toBe(false)
    expect(store.refreshTrigger).toBe(0)
  })

  describe('refresh', () => {
    it('populates items/total from the response and resets loading', async () => {
      getDemandsMock.mockResolvedValue(
        page([makeMadeItemDemandResponse({ id: 1 }), makeMadeItemDemandResponse({ id: 2 })], 2),
      )
      const store = useMadeItemsDemandsStore()

      const promise = store.refresh({ limit: 25 })
      expect(store.loading).toBe(true)
      await promise

      expect(getDemandsMock).toHaveBeenCalledWith({ limit: 25 })
      expect(store.items).toHaveLength(2)
      expect(store.total).toBe(2)
      expect(store.loading).toBe(false)
    })

    it('a failed refresh surfaces through error without throwing', async () => {
      getDemandsMock.mockRejectedValueOnce(new Error('network error'))
      const store = useMadeItemsDemandsStore()

      await store.refresh()

      expect(store.loading).toBe(false)
      expect(store.items).toEqual([])
    })
  })

  it('triggerRefresh increments refreshTrigger each call', () => {
    const store = useMadeItemsDemandsStore()
    store.triggerRefresh()
    store.triggerRefresh()
    expect(store.refreshTrigger).toBe(2)
  })

  it('clear resets items and total', async () => {
    getDemandsMock.mockResolvedValue(page([makeMadeItemDemandResponse()], 1))
    const store = useMadeItemsDemandsStore()
    await store.refresh()

    store.clear()

    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
  })

  it('create delegates to the API without mutating local state', async () => {
    const created = makeMadeItemDemandResponse({ id: 42 })
    createMock.mockResolvedValue(created)
    const store = useMadeItemsDemandsStore()

    const payload: MadeItemDemandCreateRequest = {
      made_item_id: 1,
      project_id: 1,
      quantity: 5,
      unit: 'PCS',
    }
    const result = await store.create(payload)

    expect(createMock).toHaveBeenCalledWith(payload)
    expect(result).toBe(created)
    expect(store.items).toEqual([])
  })

  it('update calls the API and replaces the matching item in the cached list', async () => {
    getDemandsMock.mockResolvedValue(page([makeMadeItemDemandResponse({ id: 1, quantity: 5 })], 1))
    const store = useMadeItemsDemandsStore()
    await store.refresh()

    const updated = makeMadeItemDemandResponse({ id: 1, quantity: 9 })
    updateMock.mockResolvedValue(updated)
    const payload: MadeItemDemandUpdateRequest = { quantity: 9, unit: 'PCS' }

    const result = await store.update(1, payload)

    expect(updateMock).toHaveBeenCalledWith(1, payload)
    expect(result).toBe(updated)
    expect(store.items[0]).toEqual(updated)
  })

  it('update is a no-op on the cached list when the item is not loaded', async () => {
    const updated = makeMadeItemDemandResponse({ id: 999, quantity: 9 })
    updateMock.mockResolvedValue(updated)
    const store = useMadeItemsDemandsStore()

    await store.update(999, { quantity: 9, unit: 'PCS' })

    expect(store.items).toEqual([])
  })

  it('updateStatus calls the API and replaces the item in the cached list', async () => {
    getDemandsMock.mockResolvedValue(
      page([makeMadeItemDemandResponse({ id: 1, status: 'open' })], 1),
    )
    const store = useMadeItemsDemandsStore()
    await store.refresh()

    const updated = makeMadeItemDemandResponse({ id: 1, status: 'canceled' })
    updateStatusMock.mockResolvedValue(updated)

    const result = await store.updateStatus(1, 'canceled')

    expect(updateStatusMock).toHaveBeenCalledWith(1, 'canceled')
    expect(result).toBe(updated)
    expect(store.items[0]?.status).toBe('canceled')
  })

  it('setBucket calls the API and replaces the item in the cached list', async () => {
    getDemandsMock.mockResolvedValue(
      page([makeMadeItemDemandResponse({ id: 1, bucket_id: null })], 1),
    )
    const store = useMadeItemsDemandsStore()
    await store.refresh()

    const updated = makeMadeItemDemandResponse({ id: 1, bucket_id: 7 })
    setBucketMock.mockResolvedValue(updated)

    const result = await store.setBucket(1, 7)

    expect(setBucketMock).toHaveBeenCalledWith(1, 7)
    expect(result).toBe(updated)
    expect(store.items[0]?.bucket_id).toBe(7)
  })

  it('fetchCancelImpact delegates to the API without mutating local state', async () => {
    const impact = makeImpact({ demand_item_id: 1 })
    cancelImpactMock.mockResolvedValue(impact)
    const store = useMadeItemsDemandsStore()

    const result = await store.fetchCancelImpact(1)

    expect(cancelImpactMock).toHaveBeenCalledWith(1)
    expect(result).toBe(impact)
    expect(store.items).toEqual([])
  })

  it('remove deletes via the API and drops the item from items/total', async () => {
    getDemandsMock.mockResolvedValue(
      page([makeMadeItemDemandResponse({ id: 1 }), makeMadeItemDemandResponse({ id: 2 })], 2),
    )
    const store = useMadeItemsDemandsStore()
    await store.refresh()
    deleteMock.mockResolvedValue(makeMadeItemDemandResponse({ id: 1 }))

    await store.remove(1)

    expect(deleteMock).toHaveBeenCalledWith(1)
    expect(store.items.map((i) => i.id)).toEqual([2])
    expect(store.total).toBe(1)
  })

  it('remove never lets total go negative', async () => {
    deleteMock.mockResolvedValue(makeMadeItemDemandResponse({ id: 1 }))
    const store = useMadeItemsDemandsStore()

    await store.remove(1)

    expect(store.total).toBe(0)
  })

  it('replaceItem updates only the matching row, leaving others untouched', async () => {
    getDemandsMock.mockResolvedValue(
      page(
        [
          makeMadeItemDemandResponse({ id: 1, quantity: 1 }),
          makeMadeItemDemandResponse({ id: 2, quantity: 2 }),
        ],
        2,
      ),
    )
    const store = useMadeItemsDemandsStore()
    await store.refresh()

    store.replaceItem(makeMadeItemDemandResponse({ id: 2, quantity: 99 }))

    expect(store.items.find((i) => i.id === 1)?.quantity).toBe(1)
    expect(store.items.find((i) => i.id === 2)?.quantity).toBe(99)
  })
})
