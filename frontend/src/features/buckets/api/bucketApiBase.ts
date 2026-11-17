import type { BucketResourceType } from '../types/bucketResponse'

/**
 * Each resource type has its own bucket endpoints at its own base path. The
 * paths stay literal so `webApi` can check every call built from them.
 */
export const BUCKET_API_BASE = {
  bought_item_demand: '/bought-items-demand-buckets',
  made_item_demand: '/made-items-demand-buckets',
  source_item_demand: '/source-item-demand-buckets',
} as const satisfies Record<BucketResourceType, string>
