<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import NumberRangeFilter from '@/shared/components/table-filters/NumberRangeFilter.vue'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useNumberRangeFilter } from '@/shared/composables/useNumberRangeFilter'

import LotDateRangeFilter from './LotDateRangeFilter.vue'
import LotFilterSelect from './LotFilterSelect.vue'
import { useProductionLotsFiltersStore } from '../../stores/productionLotsFiltersStore'
import { encodeStepMethod } from '../../utils/lotFilterParams'
import { STEP_DISPLAY_STATUSES } from '../../../utils/lotStatus'

import type { StepCellKind } from '../../utils/lotStepColumns'
import { localizeLabel } from '@/shared/utils/localizeLabel'

// The row filter of one step column, mirroring LotStepCellBody: the kind
// picks the input, and every input reads and writes the lots filters store
// directly, so the table only has to place the cell.
defineProps<{
  kind: StepCellKind
}>()

const { t } = useI18n()
const filtersStore = useProductionLotsFiltersStore()
const {
  stepMethod,
  stepStatus,
  stepSetupMin,
  stepSetupMax,
  stepPerPieceMin,
  stepPerPieceMax,
  stepPlannedStartFrom,
  stepPlannedStartTo,
  stepPlannedEndFrom,
  stepPlannedEndTo,
  stepDeliveryFrom,
  stepDeliveryTo,
  stepNote,
} = storeToRefs(filtersStore)

const fabricationMethodsStore = useFabricationMethodsStore()
const inspectionMethodsStore = useInspectionMethodsStore()

// The method catalogues are fetched the first time the picker opens, not
// when the table mounts, so a lots list that nobody filters by method never
// pays for two catalogue requests. Pinia keeps the lists across mounts, so
// the fetch happens once per session.
function ensureMethodsLoaded(): void {
  if (fabricationMethodsStore.items.length === 0) void fabricationMethodsStore.refresh()
  if (inspectionMethodsStore.items.length === 0) void inspectionMethodsStore.refresh()
}

interface MethodOption {
  label: string
  value: string
}

interface MethodOptionGroup {
  key: 'fabrication' | 'inspection'
  label: string
  items: MethodOption[]
}

const methodOptions = computed<MethodOptionGroup[]>(() => {
  const groups: MethodOptionGroup[] = []
  if (fabricationMethodsStore.activeItems.length > 0) {
    groups.push({
      key: 'fabrication',
      label: t('production.lots.filters.fabricationMethods'),
      items: fabricationMethodsStore.activeItems.map((m) => ({
        label: localizeLabel(m.name),
        value: encodeStepMethod('fabrication', m.id),
      })),
    })
  }
  if (inspectionMethodsStore.activeItems.length > 0) {
    groups.push({
      key: 'inspection',
      label: t('production.lots.filters.inspectionMethods'),
      items: inspectionMethodsStore.activeItems.map((m) => ({
        label: localizeLabel(m.name),
        value: encodeStepMethod('inspection', m.id),
      })),
    })
  }
  return groups
})

const methodsLoading = computed(
  () => fabricationMethodsStore.loading || inspectionMethodsStore.loading,
)

const statusOptions = computed(() =>
  STEP_DISPLAY_STATUSES.map((key) => ({
    label: t(`production.lots.positionStatus.${key}`),
    value: key,
  })),
)

const setupRange = useNumberRangeFilter(stepSetupMin, stepSetupMax)
const perPieceRange = useNumberRangeFilter(stepPerPieceMin, stepPerPieceMax)
const plannedStartRange = useDateRangeFilter(stepPlannedStartFrom, stepPlannedStartTo)
const plannedEndRange = useDateRangeFilter(stepPlannedEndFrom, stepPlannedEndTo)
const deliveryRange = useDateRangeFilter(stepDeliveryFrom, stepDeliveryTo)
</script>

<template>
  <Select
    v-if="kind === 'method'"
    v-model="stepMethod"
    :aria-label="t('production.lots.detail.steps.method')"
    :options="methodOptions"
    option-label="label"
    option-value="value"
    option-group-label="label"
    option-group-children="items"
    :loading="methodsLoading"
    :placeholder="t('production.lots.filters.any')"
    show-clear
    filter
    size="small"
    fluid
    @before-show="ensureMethodsLoaded"
  />
  <LotFilterSelect
    v-else-if="kind === 'status'"
    v-model="stepStatus"
    :aria-label="t('production.lots.columns.status')"
    :options="statusOptions"
    option-label="label"
    option-value="value"
  />
  <NumberRangeFilter
    v-else-if="kind === 'setup'"
    v-model="setupRange"
    :column="t('production.lots.columns.stepSetup')"
    :unit="t('production.lots.filters.minutesShort')"
    :placeholder="t('production.lots.filters.any')"
  />
  <NumberRangeFilter
    v-else-if="kind === 'perPiece'"
    v-model="perPieceRange"
    :fraction-digits="2"
    :column="t('production.lots.columns.stepPerPiece')"
    :unit="t('production.lots.filters.minutesShort')"
    :placeholder="t('production.lots.filters.any')"
  />
  <LotDateRangeFilter v-else-if="kind === 'plannedStart'" v-model="plannedStartRange" />
  <LotDateRangeFilter v-else-if="kind === 'plannedDate'" v-model="plannedEndRange" />
  <LotDateRangeFilter v-else-if="kind === 'deliveryDate'" v-model="deliveryRange" />
  <InputText
    v-else-if="kind === 'note'"
    v-model="stepNote"
    :placeholder="t('production.lots.filters.searchBy')"
    size="small"
    fluid
  />
</template>
