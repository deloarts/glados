import type { Schemas } from '@/core/api/generated'

export type SourceItemDemandStatus = Schemas['SourceItemDemandStatus']

/**
 * bucket_id carries only the id; names and colors come from the buckets
 * store, so a rename shows without refetching.
 */
export type SourceItemDemandResponse = Schemas['SourceItemDemandResponse']
