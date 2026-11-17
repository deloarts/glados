import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { BucketResourceType, BucketResponse } from '../types/bucketResponse'
import type { BucketFilterParams } from '../types/bucketRequest'
import { BUCKET_API_BASE } from './bucketApiBase'

export async function getBuckets(
  resourceType: BucketResourceType,
  params?: BucketFilterParams,
): Promise<PageResponse<BucketResponse>> {
  return webApi.get(BUCKET_API_BASE[resourceType], { query: params })
}
