import { useMachineCapability } from '../../composables/useMachineCapability'

import type { Ref } from 'vue'
import type { MachinePoolResponse } from '@/features/production-machines'
import type { LotPositionResponse } from '../../types/productionLotsResponse'
import { sortedSteps } from '../../utils/lotStepDisplay'
import { localizeLabel } from '@/shared/utils/localizeLabel'

// Position helpers for the auto-pool flow of both Manage Production panels.
export function useLotPositionAssignmentHelpers(pools: Ref<MachinePoolResponse[]>) {
  const { positionRequiresQaMachine, getRequiredMethodIds, autoPoolForPosition } =
    useMachineCapability()

  function positionRequiresMachineAssignment(position: LotPositionResponse): boolean {
    return positionRequiresQaMachine(position) || getRequiredMethodIds(position).size > 0
  }

  function resolvedPoolFor(position: LotPositionResponse): MachinePoolResponse | null {
    return autoPoolForPosition(position, pools.value)
  }

  // All machine-requiring method names of the position, for the "no pool
  // covers X + Y" message.
  function uncoveredMethodNames(position: LotPositionResponse): string[] {
    if (positionRequiresQaMachine(position)) {
      return [
        ...new Set(
          (position.steps ?? [])
            .filter((s) => s.role === 'inspection')
            .map((s) => localizeLabel(s.inspection_method_name)),
        ),
      ]
    }
    const ids = getRequiredMethodIds(position)
    return [
      ...new Set(
        (position.steps ?? [])
          .filter((s) => s.fabrication_method_id !== null && ids.has(s.fabrication_method_id))
          .map((s) => localizeLabel(s.fabrication_method_name)),
      ),
    ]
  }

  return {
    sortedSteps,
    positionRequiresMachineAssignment,
    resolvedPoolFor,
    uncoveredMethodNames,
  }
}
