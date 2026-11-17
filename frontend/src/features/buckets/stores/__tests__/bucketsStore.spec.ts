import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import type { BucketCreateRequest, BucketFilterParams, BucketUpdateRequest } from '../../types/bucketRequest'
import type { BucketResourceType, BucketResponse } from '../../types/bucketResponse'

const getBucketsMock =
  vi.fn<(resourceType: BucketResourceType, params?: BucketFilterParams) => Promise<PageResponse<BucketResponse>>>()
const createBucketMock =
  vi.fn<(resourceType: BucketResourceType, payload: BucketCreateRequest) => Promise<BucketResponse>>()
const updateBucketMock =
  vi.fn<
    (
      resourceType: BucketResourceType,
      bucketId: number,
      payload: BucketUpdateRequest,
    ) => Promise<BucketResponse>
  >()
const deleteBucketMock = vi.fn<(resourceType: BucketResourceType, bucketId: number) => Promise<BucketResponse>>()

vi.mock('../../api/getBuckets', () => ({
  getBuckets: (resourceType: BucketResourceType, params?: BucketFilterParams) =>
    getBucketsMock(resourceType, params),
}))
vi.mock('../../api/createBucket', () => ({
  createBucket: (resourceType: BucketResourceType, payload: BucketCreateRequest) =>
    createBucketMock(resourceType, payload),
}))
vi.mock('../../api/updateBucket', () => ({
  updateBucket: (resourceType: BucketResourceType, bucketId: number, payload: BucketUpdateRequest) =>
    updateBucketMock(resourceType, bucketId, payload),
}))
vi.mock('../../api/deleteBucket', () => ({
  deleteBucket: (resourceType: BucketResourceType, bucketId: number) =>
    deleteBucketMock(resourceType, bucketId),
}))

import { useBucketsStore } from '../bucketsStore'

function makeBucket(overrides: Partial<BucketResponse> = {}): BucketResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    name: 'Urgent',
    color: '#ef4444',
    creator_id: 1,
    ...overrides,
  }
}

function page(items: BucketResponse[], total = items.length): PageResponse<BucketResponse> {
  return { items, total, limit: 200, skip: 0 }
}

describe('useBucketsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getBucketsMock.mockReset()
    createBucketMock.mockReset()
    updateBucketMock.mockReset()
    deleteBucketMock.mockReset()
  })

  it('starts with empty per-resource-type lists', () => {
    const store = useBucketsStore()
    expect(store.items.bought_item_demand).toEqual([])
    expect(store.items.made_item_demand).toEqual([])
    expect(store.items.source_item_demand).toEqual([])
  })

  it('fetch populates only the requested resource type, scoped to its own base path', async () => {
    getBucketsMock.mockResolvedValue(page([makeBucket()]))
    const store = useBucketsStore()

    await store.fetch('bought_item_demand')

    expect(getBucketsMock).toHaveBeenCalledWith('bought_item_demand', expect.objectContaining({ limit: API_MAX_PAGE_SIZE }))
    expect(store.items.bought_item_demand).toHaveLength(1)
    expect(store.items.made_item_demand).toEqual([])
    expect(store.loading.bought_item_demand).toBe(false)
  })

  it('byId looks up a fetched bucket scoped by resource type', async () => {
    getBucketsMock.mockResolvedValue(page([makeBucket({ id: 5, name: 'Rework' })]))
    const store = useBucketsStore()

    await store.fetch('bought_item_demand')

    expect(store.byId.bought_item_demand[5]?.name).toBe('Rework')
    expect(store.byId.made_item_demand[5]).toBeUndefined()
  })

  it('create appends the new bucket to the resource type it was created for', async () => {
    createBucketMock.mockResolvedValue(makeBucket({ id: 2, name: 'New' }))
    const store = useBucketsStore()

    const created = await store.create('bought_item_demand', { name: 'New', color: '#ef4444' })

    expect(createBucketMock).toHaveBeenCalledWith('bought_item_demand', { name: 'New', color: '#ef4444' })
    expect(created.id).toBe(2)
    expect(store.items.bought_item_demand.map((b) => b.id)).toEqual([2])
  })

  it('update replaces the bucket in place', async () => {
    getBucketsMock.mockResolvedValue(page([makeBucket({ id: 1, name: 'Old' })]))
    const store = useBucketsStore()
    await store.fetch('bought_item_demand')

    updateBucketMock.mockResolvedValue(makeBucket({ id: 1, name: 'Renamed' }))
    await store.update('bought_item_demand', 1, { name: 'Renamed', color: '#ef4444' })

    expect(store.items.bought_item_demand[0]?.name).toBe('Renamed')
  })

  it('remove deletes the bucket from its resource type list', async () => {
    getBucketsMock.mockResolvedValue(page([makeBucket({ id: 1 })]))
    const store = useBucketsStore()
    await store.fetch('bought_item_demand')

    deleteBucketMock.mockResolvedValue(makeBucket({ id: 1 }))
    await store.remove('bought_item_demand', 1)

    expect(store.items.bought_item_demand).toEqual([])
  })

  it('requestCreate bumps createRequestTrigger so a mounted BucketsMenu can react', () => {
    const store = useBucketsStore()
    const before = store.createRequestTrigger

    store.requestCreate()

    expect(store.createRequestTrigger).toBe(before + 1)
  })
})
