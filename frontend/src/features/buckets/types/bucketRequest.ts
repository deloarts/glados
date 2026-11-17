import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

// The bought, made and source item bucket lists take the same query.
export type BucketFilterParams = QueryOf<'/bought-items-demand-buckets'>

export type BucketCreateRequest = Schemas['DemandBucketCreateRequest']

/** Name and color are always sent together. */
export type BucketUpdateRequest = Schemas['DemandBucketUpdateRequest']
