import { webApi } from '@/core/api/webRequest'

import type { BucketUpdateRequest } from '../types/bucketRequest'
import type { BucketResourceType, BucketResponse } from '../types/bucketResponse'
import { BUCKET_API_BASE } from './bucketApiBase'

export async function updateBucket(
  resourceType: BucketResourceType,
  bucketId: number,
  payload: BucketUpdateRequest,
): Promise<BucketResponse> {
  return webApi.put(`${BUCKET_API_BASE[resourceType]}/{bucket_id}`, {
    path: { bucket_id: bucketId },
    body: payload,
  })
}
