import type { ArticleGroupResponse } from '@/features/article-groups'
import type { FabricationMethodResponse } from '@/features/fabrication-methods'
import type { Schemas } from '@/core/api/generated'

export type { ArticleGroupResponse, FabricationMethodResponse }

/**
 * The web response adds external_lead_time_days, which stays off the frozen
 * PAT contract.
 */
export type SupplierResponse = Schemas['SupplierWebResponse']
