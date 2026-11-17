import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { getBuckets } from '../api/getBuckets'
import { createBucket } from '../api/createBucket'
import { updateBucket } from '../api/updateBucket'
import { deleteBucket } from '../api/deleteBucket'

import type { BucketCreateRequest, BucketUpdateRequest } from '../types/bucketRequest'
import type { BucketResourceType, BucketResponse } from '../types/bucketResponse'

const RESOURCE_TYPES: BucketResourceType[] = [
  'bought_item_demand',
  'made_item_demand',
  'source_item_demand',
]

function emptyByResourceType<T>(value: () => T): Record<BucketResourceType, T> {
  const out = {} as Record<BucketResourceType, T>
  for (const type of RESOURCE_TYPES) {
    out[type] = value()
  }
  return out
}

// Generic across the demand kinds. Each resource type is its own backend
// slice with its own ids, so every collection is keyed by type.
export const useBucketsStore = defineStore('buckets', () => {
  const items = ref<Record<BucketResourceType, BucketResponse[]>>(emptyByResourceType(() => []))

  function makeFetcher(type: BucketResourceType) {
    return useSequencedFetch(() => getBuckets(type, { limit: API_MAX_PAGE_SIZE }))
  }

  // One sequenced fetcher per resource type, so a fetch for one type never
  // discards another type's in-flight fetch.
  const fetchers = {} as Record<BucketResourceType, ReturnType<typeof makeFetcher>>
  for (const type of RESOURCE_TYPES) {
    fetchers[type] = makeFetcher(type)
  }

  const loading = computed<Record<BucketResourceType, boolean>>(() => {
    const out = {} as Record<BucketResourceType, boolean>
    for (const type of RESOURCE_TYPES) {
      out[type] = fetchers[type].loading.value
    }
    return out
  })

  // Bumped by requestCreate() so a mounted BucketsMenu opens its new-bucket
  // row, e.g. from the table's context menu.
  const createRequestTrigger = ref(0)

  const byId = computed<Record<BucketResourceType, Record<number, BucketResponse>>>(() => {
    const out = {} as Record<BucketResourceType, Record<number, BucketResponse>>
    for (const type of RESOURCE_TYPES) {
      const map: Record<number, BucketResponse> = {}
      for (const bucket of items.value[type]) {
        map[bucket.id] = bucket
      }
      out[type] = map
    }
    return out
  })

  async function fetch(resourceType: BucketResourceType): Promise<void> {
    const response = await fetchers[resourceType].run()
    if (!response) return

    items.value[resourceType] = response.items
  }

  async function create(
    resourceType: BucketResourceType,
    payload: BucketCreateRequest,
  ): Promise<BucketResponse> {
    const created = await createBucket(resourceType, payload)
    items.value[resourceType] = [...items.value[resourceType], created]
    return created
  }

  async function update(
    resourceType: BucketResourceType,
    bucketId: number,
    payload: BucketUpdateRequest,
  ): Promise<BucketResponse> {
    const updated = await updateBucket(resourceType, bucketId, payload)
    const list = items.value[resourceType]
    const index = list.findIndex((b) => b.id === bucketId)
    if (index !== -1) {
      list[index] = updated
    }
    return updated
  }

  async function remove(resourceType: BucketResourceType, bucketId: number): Promise<void> {
    await deleteBucket(resourceType, bucketId)
    items.value[resourceType] = items.value[resourceType].filter((b) => b.id !== bucketId)
  }

  function requestCreate(): void {
    createRequestTrigger.value++
  }

  return {
    items,
    loading,
    createRequestTrigger,
    byId,
    fetch,
    create,
    update,
    remove,
    requestCreate,
  }
})
