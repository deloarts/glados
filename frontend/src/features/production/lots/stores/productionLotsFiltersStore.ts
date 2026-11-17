import { ref } from 'vue'

import { createFiltersStore } from '@/shared/stores/createFiltersStore'
import type { FiltersStoreBase } from '@/shared/stores/createFiltersStore'

import type { SourceItemDemandStatus } from '@/features/source-items'

import type { LotPriority, LotStatus } from '../../types/productionLotsResponse'
import type { LotSortBy, StepDisplayStatus } from '../../types/productionLotsRequest'

export type LotGroupBy = 'status' | 'priority' | 'project' | null

// A type alias, since createFiltersStore needs an implicit index signature
// that an interface does not get.
type ProductionLotsFilterFields = {
  search: string
  projectNumber: string
  itemArticleName: string
  itemPartNumber: string
  statusFilter: LotStatus | null
  priorityFilter: LotPriority | null
  creatorFilter: number | null
  createdFrom: Date | null
  createdTo: Date | null
  changedByFilter: number | null
  changedFrom: Date | null
  changedTo: Date | null
  hideCompleted: boolean
  hideCanceled: boolean
  // Lots not yet fully planned, sent as `statuses` and combinable with the
  // status dropdown.
  needsAssignmentOnly: boolean
  // Lots with a pending source approval.
  needsApprovalOnly: boolean
  // Set by opening any Manage panel, narrowing the list to lots with
  // something to act on. A field of its own, so Clear can widen the list
  // while the panel stays open.
  actionableFilterArmed: boolean
  // Set by Manage Production, narrowing to positions the selected machine
  // or pool can cover; Clear can switch it off the same way.
  coverageFilterArmed: boolean
  // Lot-level column filters.
  lotNumber: string
  targetDateFrom: Date | null
  targetDateTo: Date | null
  quantityMin: number | null
  quantityMax: number | null
  // Source columns: free text over the source item, or the dimension and
  // type lines of its cell on their own, the input demand's status, and the
  // material's delivery date range.
  sourceText: string
  sourceDimension: string
  sourceType: string
  sourceStatus: SourceItemDemandStatus | null
  sourceDeliveryFrom: Date | null
  sourceDeliveryTo: Date | null
  // Step columns. All of them must match the same position of a lot. The
  // method is one grouped picker over fabrication and inspection methods,
  // stored encoded as `fabrication:<id>` / `inspection:<id>` and decoded
  // into the two mutually exclusive query params by the params builder.
  stepMethod: string | null
  stepStatus: StepDisplayStatus | null
  stepSetupMin: number | null
  stepSetupMax: number | null
  stepPerPieceMin: number | null
  stepPerPieceMax: number | null
  stepPlannedStartFrom: Date | null
  stepPlannedStartTo: Date | null
  stepPlannedEndFrom: Date | null
  stepPlannedEndTo: Date | null
  stepDeliveryFrom: Date | null
  stepDeliveryTo: Date | null
  stepNote: string
}

function extend(base: FiltersStoreBase<ProductionLotsFilterFields, LotSortBy, true>) {
  const groupBy = ref<LotGroupBy>(null)
  const simpleMode = ref(false)
  // Off is Column Mode with every lot's steps collapsed into one set of step
  // columns; on spreads them into one column group each.
  const widescreenMode = ref(false)
  // Override for the Manage panels' smart filter, on by default. It does
  // not count as an active filter, but Clear forces it off, since resetting
  // to its default would not widen the list.
  const smartFilterEnabled = ref(true)

  function toggleSmartFilter(): void {
    smartFilterEnabled.value = !smartFilterEnabled.value
  }

  // Grouping needs the DataTable's rowGroupMode, which only Widescreen Mode
  // uses, so picking a group switches to it.
  function setGroupBy(value: Exclude<LotGroupBy, null>): void {
    groupBy.value = groupBy.value === value ? null : value
    if (groupBy.value) widescreenMode.value = true
  }

  function clearGroupBy(): void {
    groupBy.value = null
  }

  function toggleHideCompleted(): void {
    base.hideCompleted.value = !base.hideCompleted.value
  }

  function toggleHideCanceled(): void {
    base.hideCanceled.value = !base.hideCanceled.value
  }

  function toggleNeedsAssignmentOnly(): void {
    base.needsAssignmentOnly.value = !base.needsAssignmentOnly.value
  }

  function toggleNeedsApprovalOnly(): void {
    base.needsApprovalOnly.value = !base.needsApprovalOnly.value
  }

  function toggleSimpleMode(): void {
    simpleMode.value = !simpleMode.value
  }

  // A DataTable runs one rowGroupMode at a time, so leaving Widescreen Mode
  // clears Group By.
  function toggleWidescreenMode(): void {
    widescreenMode.value = !widescreenMode.value
    if (!widescreenMode.value) groupBy.value = null
  }

  return {
    state: {
      groupBy,
      simpleMode,
      widescreenMode,
      smartFilterEnabled,
      setGroupBy,
      clearGroupBy,
      toggleHideCompleted,
      toggleHideCanceled,
      toggleNeedsAssignmentOnly,
      toggleNeedsApprovalOnly,
      toggleSimpleMode,
      toggleWidescreenMode,
      toggleSmartFilter,
    },
    onClear: () => {
      groupBy.value = null
      // Forced off rather than reset (see smartFilterEnabled).
      smartFilterEnabled.value = false
    },
  }
}

// Every field is scalar, so the default equality check is correct.
export const useProductionLotsFiltersStore = createFiltersStore<
  ProductionLotsFilterFields,
  LotSortBy,
  true,
  ReturnType<typeof extend>['state']
>('productionLotsFilters', {
  defaults: {
    search: '',
    projectNumber: '',
    itemArticleName: '',
    itemPartNumber: '',
    statusFilter: null,
    priorityFilter: null,
    creatorFilter: null,
    createdFrom: null,
    createdTo: null,
    changedByFilter: null,
    changedFrom: null,
    changedTo: null,
    hideCompleted: false,
    hideCanceled: false,
    needsAssignmentOnly: false,
    needsApprovalOnly: false,
    actionableFilterArmed: false,
    coverageFilterArmed: false,
    lotNumber: '',
    targetDateFrom: null,
    targetDateTo: null,
    quantityMin: null,
    quantityMax: null,
    sourceText: '',
    sourceDimension: '',
    sourceType: '',
    sourceStatus: null,
    sourceDeliveryFrom: null,
    sourceDeliveryTo: null,
    stepMethod: null,
    stepStatus: null,
    stepSetupMin: null,
    stepSetupMax: null,
    stepPerPieceMin: null,
    stepPerPieceMax: null,
    stepPlannedStartFrom: null,
    stepPlannedStartTo: null,
    stepPlannedEndFrom: null,
    stepPlannedEndTo: null,
    stepDeliveryFrom: null,
    stepDeliveryTo: null,
    stepNote: '',
  },
  sortable: true,
  extend,
})
