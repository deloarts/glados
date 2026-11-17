<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { dateToParam, toLocalDayStart } from '@/core/utils/dates'
import { updateProductionOrder } from '../../api/updateProductionOrder'
import { updateOrderItem } from '@/features/orders'
import { MadeItemThumbnailCell, useMadeItemLabel } from '@/features/made-items'

import type { PlannedDateEditTarget } from '../../composables/useLotStepDeliveryInfo'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

const props = defineProps<{
  target: PlannedDateEditTarget
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  saved: []
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { format: madeItemLabel } = useMadeItemLabel()

// The end date (internal: planned_end, external: expected_delivery_date).
const date = ref<Date | null>(null)
// Internal only; a purchased item has no start.
const startDate = ref<Date | null>(null)
// Internal only: the backend computes planned_end from the start and the
// order's duration on the machine calendar.
const recomputeEnd = ref(true)
const { submitting, errorMessage, run } = useSubmitAction()

watch(visible, (isVisible) => {
  if (!isVisible || !props.target) return
  errorMessage.value = null
  recomputeEnd.value = true
  // The pickers show the day each value falls on in the tenant's timezone.
  if (props.target.kind === 'internal') {
    startDate.value = props.target.currentPlannedStart
      ? toLocalDayStart(props.target.currentPlannedStart)
      : null
    date.value = props.target.currentPlannedEnd
      ? toLocalDayStart(props.target.currentPlannedEnd)
      : null
  } else {
    startDate.value = null
    date.value = props.target.currentExpectedDeliveryDate
      ? toLocalDayStart(props.target.currentExpectedDeliveryDate)
      : null
  }
})

const fieldLabel = computed(() =>
  props.target?.kind === 'internal'
    ? t('production.lots.plannedDate.internalLabel')
    : t('production.lots.plannedDate.externalLabel'),
)

const canSubmit = computed(() => {
  if (!props.target) return false
  if (props.target.kind === 'internal') {
    if (!startDate.value) return false
    return recomputeEnd.value || date.value !== null
  }
  return date.value !== null
})

async function onSubmit(): Promise<void> {
  const target = props.target
  if (!target || !canSubmit.value) return

  await run(async () => {
    if (target.kind === 'internal') {
      // Pickers yield local midnight, so dateToParam sends the local day;
      // toISOString() would shift it for timezones ahead of UTC.
      await updateProductionOrder(target.orderId, {
        planned_start: dateToParam(startDate.value),
        planned_end: recomputeEnd.value ? null : dateToParam(date.value),
        recompute_planned_end: recomputeEnd.value,
        expected_edit_version: target.editVersion,
      })
    } else {
      await updateOrderItem(target.orderId, target.itemId, {
        quantity: target.quantity,
        unit: target.unit,
        items_per_unit: target.itemsPerUnit,
        expected_delivery_date: dateToParam(date.value),
        expected_edit_version: target.editVersion,
      })
    }
    visible.value = false
    emit('saved')
  }, t('production.lots.plannedDate.errors.unknown'))
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('production.lots.plannedDate.dialogTitle')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div class="planned-date-form">
      <div v-if="target" class="part-info-row">
        <MadeItemThumbnailCell
          :item-id="target.madeItem.id"
          :item-name="target.madeItem.partNumber"
          size="3.5rem"
          no-image-icon="mdi mdi-image-outline"
        />
        <div class="part-info-text">
          <span class="item-name">{{ target.madeItem.articleName }}</span>
          <span class="item-code">{{
            madeItemLabel(target.madeItem.partNumber, target.madeItem.revision)
          }}</span>
        </div>
      </div>

      <div v-if="target" class="step-flow">
        <div class="step-box step-box--neighbor">
          <span class="step-box-label">{{ t('production.lots.plannedDate.stepBefore') }}</span>
          <span class="step-box-value">{{
            target.prevStep?.fabricationMethodName ?? getEmptyPlaceholder()
          }}</span>
        </div>
        <i class="mdi mdi-arrow-right-thin step-flow-arrow" aria-hidden="true" />
        <div class="step-box step-box--current">
          <span class="step-box-label">{{ t('production.lots.plannedDate.thisStep') }}</span>
          <span class="step-box-value">{{ target.thisStep.fabricationMethodName }}</span>
        </div>
        <i class="mdi mdi-arrow-right-thin step-flow-arrow" aria-hidden="true" />
        <div class="step-box step-box--neighbor">
          <span class="step-box-label">{{ t('production.lots.plannedDate.stepAfter') }}</span>
          <span class="step-box-value">{{
            target.nextStep?.fabricationMethodName ?? getEmptyPlaceholder()
          }}</span>
        </div>
      </div>

      <div v-if="target?.kind === 'internal'" class="field">
        <label :for="`${uid}-internal-start-label`">{{ t('production.lots.plannedDate.internalStartLabel') }}</label>
        <DatePicker v-model="startDate" :input-id="`${uid}-internal-start-label`" show-button-bar fluid />
      </div>
      <div class="field">
        <label :for="`${uid}-date`">{{ fieldLabel }}</label>
        <DatePicker v-model="date" :input-id="`${uid}-date`" show-button-bar fluid :disabled="recomputeEnd" />
      </div>
      <p v-if="target?.kind === 'internal'" class="field-hint">
        {{ t('production.lots.plannedDate.internalHint') }}
      </p>

      <template v-if="target?.kind === 'internal'">
        <label class="checkbox-toggle">
          <Checkbox v-model="recomputeEnd" binary />
          <span>
            {{ t('production.lots.plannedDate.recomputeEnd') }}
            <small class="field-hint">{{
              t('production.lots.plannedDate.recomputeEndHint')
            }}</small>
          </span>
        </label>
      </template>

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>
    </div>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" outlined @click="visible = false" />
      <Button
        :label="t('common.save')"
        :loading="submitting"
        :disabled="!canSubmit"
        @click="onSubmit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.planned-date-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.part-info-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.part-info-text {
  display: flex;
  flex-direction: column;

  .item-name {
    font-weight: 600;
  }

  .item-code {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }
}

.step-flow {
  display: flex;
  align-items: stretch;
  gap: var(--space-2);
}

.step-flow-arrow {
  align-self: center;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-lg);
}

.step-box {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-2);
  border-radius: var(--p-content-border-radius);
  border: 1px solid var(--p-content-border-color);
}

.step-box-label {
  font-size: var(--font-size-xs);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--p-text-muted-color);
}

.step-box-value {
  font-size: var(--font-size-sm);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

// Before/after boxes are greyed out: context only, not editable here.
.step-box--neighbor {
  background: var(--p-surface-50);

  .step-box-value {
    color: var(--p-text-muted-color);
    font-weight: 400;
  }
}

.p-dark .step-box--neighbor {
  background: var(--p-surface-900);
}

.step-box--current {
  border-color: var(--p-primary-color);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-hint {
  display: block;
  margin: 0;
  font-weight: 400;
}

.checkbox-toggle {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}
</style>
