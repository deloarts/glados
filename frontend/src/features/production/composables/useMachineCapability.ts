import type { ProductionMachineResponse } from '@/features/production-machines'
import type { MachinePoolResponse } from '@/features/production-machines'
import type { LotPositionResponse } from '../types/productionLotsResponse'
import { sortedBySequence } from '../utils/sequence'

// Capability matching for assigning a lot position to machines and pools.
// The rules mirror the backend, see docs/reference/scheduling.md.
export function useMachineCapability() {
  // Manual steps never constrain machine choice.
  function getRequiredMethodIds(position: Pick<LotPositionResponse, 'steps'> | null): Set<number> {
    return new Set(
      (position?.steps ?? [])
        .filter((s) => s.fabrication_method_requires_machine)
        .map((s) => s.fabrication_method_id)
        .filter((id): id is number => id !== null),
    )
  }

  // An inspection step is always its own position and may only go to a QA
  // machine.
  function positionRequiresQaMachine(position: Pick<LotPositionResponse, 'steps'> | null): boolean {
    return (position?.steps ?? []).some((s) => s.role === 'inspection')
  }

  // A position whose steps all skip machines is queued machine-less. Without
  // this check an empty required set would count as covered by any machine.
  function positionIsManual(position: Pick<LotPositionResponse, 'steps'> | null): boolean {
    const steps = position?.steps ?? []
    return steps.length > 0 && steps.every((s) => !s.fabrication_method_requires_machine)
  }

  function getCapableMachines(
    position: LotPositionResponse | null,
    machines: ProductionMachineResponse[],
  ): ProductionMachineResponse[] {
    if (positionRequiresQaMachine(position)) {
      return machines.filter((m) => m.is_qa_machine)
    }
    if (positionIsManual(position)) return []
    const requiredMethodIds = getRequiredMethodIds(position)
    return machines.filter((m) => {
      if (m.is_qa_machine) return false
      const ids = new Set(m.fabrication_method_ids)
      return [...requiredMethodIds].every((id) => ids.has(id))
    })
  }

  function machineCoversPosition(
    position: Pick<LotPositionResponse, 'steps'>,
    machine: ProductionMachineResponse,
  ): boolean {
    if (positionRequiresQaMachine(position) !== !!machine.is_qa_machine) return false
    if (machine.is_qa_machine) return true
    if (positionIsManual(position)) return false
    const ids = new Set(machine.fabrication_method_ids)
    return [...getRequiredMethodIds(position)].every((id) => ids.has(id))
  }

  // A pool covers only the methods every member can do.
  function getPoolCapability(pool: MachinePoolResponse): Set<number> {
    if (pool.machines.length === 0) return new Set()
    return pool.machines
      .map((m) => new Set(m.fabrication_method_ids))
      .reduce((intersection, ids) => new Set([...intersection].filter((id) => ids.has(id))))
  }

  function poolCoversPosition(
    position: Pick<LotPositionResponse, 'steps'>,
    pool: MachinePoolResponse,
  ): boolean {
    if (positionRequiresQaMachine(position)) return false
    if (positionIsManual(position)) return false
    const capability = getPoolCapability(pool)
    return [...getRequiredMethodIds(position)].every((id) => capability.has(id))
  }

  function candidatePoolsForPosition(
    position: LotPositionResponse | null,
    pools: MachinePoolResponse[],
  ): MachinePoolResponse[] {
    if (!position) return []
    return pools.filter((pool) => poolCoversPosition(position, pool))
  }

  // Picks the pool for a position nobody targeted explicitly: fewest methods,
  // then fewest members, then lowest id, so the tightest fit wins. Null when
  // no pool covers the position.
  function autoPoolForPosition(
    position: LotPositionResponse | null,
    pools: MachinePoolResponse[],
  ): MachinePoolResponse | null {
    const candidates = candidatePoolsForPosition(position, pools)
    if (candidates.length === 0) return null
    return [...candidates].sort((a, b) => {
      const capacityDiff = getPoolCapability(a).size - getPoolCapability(b).size
      if (capacityDiff !== 0) return capacityDiff
      const memberDiff = a.machines.length - b.machines.length
      if (memberDiff !== 0) return memberDiff
      return a.id - b.id
    })[0]!
  }

  // Steps usually outsourced; internal assignment is allowed but warned about.
  function getExternalRequiredSteps(position: LotPositionResponse | null) {
    return (position?.steps ?? []).filter((s) => s.fabrication_method_required_external)
  }

  function positionHasExternalMethods(position: LotPositionResponse | null): boolean {
    return getExternalRequiredSteps(position).length > 0
  }

  // Supplier hint for a new order: the first required_external step's default
  // supplier, else any step's default supplier.
  function getPreferredSupplierId(position: LotPositionResponse | null): number | null {
    const steps = sortedBySequence(position?.steps)
    const externalWithSupplier = steps.find(
      (s) => s.fabrication_method_required_external && s.fabrication_method_default_supplier_id,
    )
    if (externalWithSupplier)
      return externalWithSupplier.fabrication_method_default_supplier_id ?? null
    const anyWithSupplier = steps.find((s) => s.fabrication_method_default_supplier_id)
    return anyWithSupplier?.fabrication_method_default_supplier_id ?? null
  }

  return {
    getRequiredMethodIds,
    positionRequiresQaMachine,
    positionIsManual,
    getCapableMachines,
    machineCoversPosition,
    getPoolCapability,
    poolCoversPosition,
    candidatePoolsForPosition,
    autoPoolForPosition,
    getExternalRequiredSteps,
    positionHasExternalMethods,
    getPreferredSupplierId,
  }
}
