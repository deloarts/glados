import { computed, type ComputedRef } from 'vue'

export interface DemandUnitOption {
  value: string
  label: string
}

/**
 * Builds the unit dropdown options every demand create/detail form shares.
 * The forms pass in the unit codes from shared/utils/units.ts and label each
 * with the long unit name from their own `t`, so the labels follow the UI
 * language.
 */
export function useDemandUnitOptions(
  unitCodes: readonly string[],
  unitLabel: (code: string) => string,
): ComputedRef<DemandUnitOption[]> {
  return computed(() => unitCodes.map((code) => ({ value: code, label: unitLabel(code) })))
}
