import { webApi } from '@/core/api/webRequest'

import type { BucketCreateRequest } from '../types/bucketRequest'
import type { BucketResourceType, BucketResponse } from '../types/bucketResponse'
import { BUCKET_API_BASE } from './bucketApiBase'

export async function createBucket(
  resourceType: BucketResourceType,
  payload: BucketCreateRequest,
): Promise<BucketResponse> {
  return webApi.post(BUCKET_API_BASE[resourceType], { body: payload })
}
