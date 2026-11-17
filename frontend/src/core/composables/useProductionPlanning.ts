/**
 * The single read point for the Production Planning feature flag.
 *
 * When off, every internal-production surface is hidden: the Production
 * section and its routes, machines, lots, production orders, and the project
 * time budget. This is presentational only, the API keeps serving those
 * endpoints, so a user who knows a URL is not locked out of data they have
 * permission for. The flag is about decluttering an installation that does no
 * internal production, not about access control; that is what permissions are
 * for.
 *
 * Defaults to enabled until /host/capabilities answers, so a section never
 * pops into view a moment after load.
 */
import { computed } from 'vue'
import type { ComputedRef } from 'vue'

import { useHostStore } from '@/core/host/stores/hostStore'

export function useProductionPlanning(): { productionPlanningEnabled: ComputedRef<boolean> } {
  const hostStore = useHostStore()
  return {
    productionPlanningEnabled: computed(() => hostStore.productionPlanningEnabled),
  }
}
