import type { Schemas } from '@/core/api/generated'

/** Frontend-only key; each resource type has its own backend base path. */
export type BucketResourceType = 'bought_item_demand' | 'made_item_demand' | 'source_item_demand'

// Which slice a bucket belongs to is implied by where it was fetched from.
export type BucketResponse = Schemas['DemandBucketResponse']
