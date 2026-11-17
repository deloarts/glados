<script setup lang="ts">
// Method cell of the lot step list: a fabrication or inspection method
// Select, depending on the step's role. Archived methods stay selectable
// (sorted last by methodOptions), and the cell flags when the step's current
// method is one of them.
import { useI18n } from 'vue-i18n'

import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { methodOptions } from '../utils/lotStepMethodOptions'

import type { LotStepPatch } from '../composables/useLotStructureDraft'
import type { LotStepResponse } from '../../types/productionLotsResponse'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

defineProps<{
  step: LotStepResponse
  readonly: boolean
  // A fabrication method change is rejected once the position is assigned.
  locked: boolean
}>()

const emit = defineEmits<{
  change: [patch: LotStepPatch]
}>()

const { t } = useI18n()
const fabricationMethodsStore = useFabricationMethodsStore()
const inspectionMethodsStore = useInspectionMethodsStore()

function isFabricationMethodArchived(id: number | null): boolean {
  if (id === null) return false
  return !!fabricationMethodsStore.getById(id)?.archived
}

function isInspectionMethodArchived(id: number | null): boolean {
  if (id === null) return false
  return !!inspectionMethodsStore.getById(id)?.archived
}
</script>

<template>
  <span
    v-tooltip.top="
      !readonly && locked ? t('production.lots.detail.steps.assignedFieldLockedTooltip') : undefined
    "
  >
    <Select
      v-if="step.role === 'fabrication'"
      :aria-label="t('production.lots.detail.steps.method')"
      :model-value="step.fabrication_method_id"
      :options="methodOptions(fabricationMethodsStore)"
      :option-label="labelName"
      option-value="id"
      :disabled="readonly || locked"
      fluid
      @update:model-value="(v) => emit('change', { fabrication_method_id: v as number })"
    >
      <template #option="{ option }">
        <span>{{ localizeLabel(option.name) }}</span>
        <ArchivedOptionTag v-if="option.archived" />
      </template>
      <template #value="{ value }">
        <span v-if="value != null">{{
          localizeLabel(fabricationMethodsStore.getById(value)?.name)
        }}</span>
        <ArchivedOptionTag v-if="isFabricationMethodArchived(value)" />
      </template>
    </Select>
    <Select
      v-else
      :aria-label="t('production.lots.detail.steps.method')"
      :model-value="step.inspection_method_id"
      :options="methodOptions(inspectionMethodsStore)"
      :option-label="labelName"
      option-value="id"
      :disabled="readonly"
      fluid
      @update:model-value="(v) => emit('change', { inspection_method_id: v as number })"
    >
      <template #option="{ option }">
        <span>{{ localizeLabel(option.name) }}</span>
        <ArchivedOptionTag v-if="option.archived" />
      </template>
      <template #value="{ value }">
        <span v-if="value != null">{{
          localizeLabel(inspectionMethodsStore.getById(value)?.name)
        }}</span>
        <ArchivedOptionTag v-if="isInspectionMethodArchived(value)" />
      </template>
    </Select>
  </span>
  <ArchivedSelectionWarning
    v-if="
      step.role === 'fabrication'
        ? isFabricationMethodArchived(step.fabrication_method_id)
        : isInspectionMethodArchived(step.inspection_method_id)
    "
  />
</template>
