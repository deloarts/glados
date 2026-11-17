import { webApi } from '@/core/api/webRequest'

import type { BucketResourceType, BucketResponse } from '../types/bucketResponse'
import { BUCKET_API_BASE } from './bucketApiBase'

// Returns the deleted bucket (not void) per the API contract.
export async function deleteBucket(
  resourceType: BucketResourceType,
  bucketId: number,
): Promise<BucketResponse> {
  return webApi.delete(`${BUCKET_API_BASE[resourceType]}/{bucket_id}`, {
    path: { bucket_id: bucketId },
  })
}
