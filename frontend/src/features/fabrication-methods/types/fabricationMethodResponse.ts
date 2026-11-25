import type { Schemas } from '@/core/api/generated'

/**
 * The web response adds lead_time_days and wait_after_minutes, which stay off
 * the frozen PAT contract.
 */
export type FabricationMethodResponse = Schemas['FabricationMethodWebResponse']
