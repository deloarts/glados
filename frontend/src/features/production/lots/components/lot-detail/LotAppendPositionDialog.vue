<script setup lang="ts">
import { computed, onMounted, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useProductionLotDetailStore } from '../../stores/productionLotDetailStore'

import type { StepRole } from '../../../types/productionLotsResponse'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const props = defineProps<{
  lotId: number
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { withErrorToast } = useErrorToast()
const detailStore = useProductionLotDetailStore()
const fabricationMethodsStore = useFabricationMethodsStore()
const inspectionMethodsStore = useInspectionMethodsStore()

onMounted(() => {
  if (fabricationMethodsStore.items.length === 0) void fabricationMethodsStore.refresh()
  if (inspectionMethodsStore.items.length === 0) void inspectionMethodsStore.refresh()
})

// Referencing an already-archived method is allowed: every method is
// selectable, archived ones sorted after live ones and tagged (see
// useArchivableOptions.ts). A freshly appended step still defaults to the
// first *live* method below, never an archived one.
const { sortedOptions: fabricationMethodOptions, isArchived: isFabricationMethodArchived } =
  useArchivableOptions(computed(() => fabricationMethodsStore.items))
const { sortedOptions: inspectionMethodOptions, isArchived: isInspectionMethodArchived } =
  useArchivableOptions(computed(() => inspectionMethodsStore.items))

function fabricationMethodById(id: number | null) {
  return fabricationMethodsStore.getById(id) ?? null
}

function inspectionMethodById(id: number | null) {
  return inspectionMethodsStore.getById(id) ?? null
}

interface AppendForm {
  role: StepRole
  fabrication_method_id: number | null
  inspection_method_id: number | null
  note: string
  estimated_setup_minutes: number | null
  estimated_minutes_per_piece: number | null
}

const appendForm = reactive<AppendForm>({
  role: 'fabrication',
  fabrication_method_id: null,
  inspection_method_id: null,
  note: '',
  estimated_setup_minutes: null,
  estimated_minutes_per_piece: null,
})
const appendSubmitting = ref(false)

const appendRoleOptions = computed(() => [
  { label: t('production.lots.detail.steps.fabricationStep'), value: 'fabrication' },
  { label: t('production.lots.inspection.label'), value: 'inspection' },
])

watch(visible, (isVisible) => {
  if (!isVisible) return
  appendForm.role = 'fabrication'
  appendForm.fabrication_method_id = fabricationMethodsStore.activeItems[0]?.id ?? null
  appendForm.inspection_method_id = inspectionMethodsStore.activeItems[0]?.id ?? null
  appendForm.note = ''
  appendForm.estimated_setup_minutes = null
  appendForm.estimated_minutes_per_piece = null
})

const canSubmitAppendPosition = computed(() =>
  appendForm.role === 'inspection'
    ? appendForm.inspection_method_id !== null
    : appendForm.fabrication_method_id !== null,
)

async function submitAppendPosition(): Promise<void> {
  if (!canSubmitAppendPosition.value) return

  appendSubmitting.value = true
  const succeeded = await withErrorToast(
    async () => {
      await detailStore.appendPosition(props.lotId, {
        steps: [
          appendForm.role === 'inspection'
            ? {
                role: 'inspection',
                inspection_method_id: appendForm.inspection_method_id,
                note: appendForm.note.trim() || null,
                estimated_setup_minutes: appendForm.estimated_setup_minutes,
                estimated_minutes_per_piece: appendForm.estimated_minutes_per_piece,
              }
            : {
                role: 'fabrication',
                fabrication_method_id: appendForm.fabrication_method_id,
                note: appendForm.note.trim() || null,
                estimated_setup_minutes: appendForm.estimated_setup_minutes,
                estimated_minutes_per_piece: appendForm.estimated_minutes_per_piece,
              },
        ],
      })
      return true
    },
    { summary: t('production.lots.detail.positions.appendError') },
  )
  if (succeeded) visible.value = false
  appendSubmitting.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('production.lots.detail.positions.append')"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <div class="append-form">
      <div class="field">
        <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- SelectButton is a group of buttons, so the label names it through aria-labelledby -->
        <label :id="`${uid}-step-type`">{{ t('production.lots.detail.steps.stepType') }}</label>
        <SelectButton
          v-model="appendForm.role"
          :aria-labelledby="`${uid}-step-type`"
          :options="appendRoleOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
        />
      </div>
      <div v-if="appendForm.role === 'fabrication'" class="field">
        <label :id="`${uid}-fabrication-method-label`" :for="`${uid}-fabrication-method`">
          {{ t('production.lots.detail.steps.fabricationMethod') }} *
        </label>
        <Select
          v-model="appendForm.fabrication_method_id"
          :input-id="`${uid}-fabrication-method`"
          :aria-labelledby="`${uid}-fabrication-method-label`"
          :options="fabricationMethodOptions"
          :option-label="labelName"
          option-value="id"
          fluid
        >
          <template #option="{ option }">
            <span>{{ localizeLabel(option.name) }}</span>
            <ArchivedOptionTag v-if="option.archived" />
          </template>
          <template #value="{ value }">
            <span v-if="value !== null">{{
              localizeLabel(fabricationMethodById(value)?.name) || getEmptyPlaceholder()
            }}</span>
            <ArchivedOptionTag v-if="isFabricationMethodArchived(fabricationMethodById(value))" />
          </template>
        </Select>
        <ArchivedSelectionWarning
          v-if="isFabricationMethodArchived(fabricationMethodById(appendForm.fabrication_method_id))"
        />
      </div>
      <div v-else class="field">
        <label :id="`${uid}-label-label`" :for="`${uid}-inspection`">{{ t('production.lots.inspection.label') }} *</label>
        <Select
          v-model="appendForm.inspection_method_id"
          :input-id="`${uid}-inspection`"
          :aria-labelledby="`${uid}-label-label`"
          :options="inspectionMethodOptions"
          :option-label="labelName"
          option-value="id"
          fluid
        >
          <template #option="{ option }">
            <span>{{ localizeLabel(option.name) }}</span>
            <ArchivedOptionTag v-if="option.archived" />
          </template>
          <template #value="{ value }">
            <span v-if="value !== null">{{
              localizeLabel(inspectionMethodById(value)?.name) || getEmptyPlaceholder()
            }}</span>
            <ArchivedOptionTag v-if="isInspectionMethodArchived(inspectionMethodById(value))" />
          </template>
        </Select>
        <ArchivedSelectionWarning
          v-if="isInspectionMethodArchived(inspectionMethodById(appendForm.inspection_method_id))"
        />
      </div>
      <div class="field">
        <label :for="`${uid}-setup-minutes`">{{ t('production.lots.detail.steps.setupMinutes') }}</label>
        <InputNumber v-model="appendForm.estimated_setup_minutes" :input-id="`${uid}-setup-minutes`" :min="0" fluid />
      </div>
      <div class="field">
        <label :for="`${uid}-per-piece-minutes`">{{ t('production.lots.detail.steps.perPieceMinutes') }}</label>
        <InputNumber
          v-model="appendForm.estimated_minutes_per_piece"
          :input-id="`${uid}-per-piece-minutes`"
          :min="0"
          :max-fraction-digits="2"
          fluid
        />
      </div>
      <div class="field">
        <label :for="`${uid}-note`">{{ t('production.lots.detail.steps.note') }}</label>
        <Textarea v-model="appendForm.note" :id="`${uid}-note`" rows="2" auto-resize fluid />
      </div>
    </div>
    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        @click="visible = false"
      />
      <Button
        :label="t('common.save')"
        :loading="appendSubmitting"
        :disabled="!canSubmitAppendPosition"
        @click="submitAppendPosition"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.append-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
