<script setup lang="ts">
import { ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { dateToParam, toLocalDayStart } from '@/core/utils/dates'
import { useProductionLotsStore } from '../../stores/productionLotsStore'

import type { LotSummaryResponse } from '../../types/productionLotsResponse'

const emit = defineEmits<{ saved: [] }>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { withErrorToast } = useErrorToast()
const lotsStore = useProductionLotsStore()

const visible = ref(false)
const lot = ref<LotSummaryResponse | null>(null)
const date = ref<Date | null>(null)
const submitting = ref(false)

function open(target: LotSummaryResponse): void {
  lot.value = target
  date.value = target.required_delivery_date
    ? toLocalDayStart(target.required_delivery_date)
    : null
  visible.value = true
}

async function onSave(): Promise<void> {
  if (!lot.value) return
  submitting.value = true
  const result = await withErrorToast(
    () =>
      lotsStore.update(lot.value!.id, {
        required_delivery_date: dateToParam(date.value),
        expected_edit_version: lot.value!.edit_version,
      }),
    { summary: t('production.lots.requiredDeliveryDialog.error') },
  )
  submitting.value = false
  if (result === undefined) return
  visible.value = false
  emit('saved')
}

defineExpose({ open })
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('production.lots.requiredDeliveryDialog.title')"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <div class="required-delivery-form">
      <div class="field">
        <label :for="`${uid}-required-delivery-dialog`">{{ t('production.lots.requiredDeliveryDialog.label') }}</label>
        <DatePicker v-model="date" :input-id="`${uid}-required-delivery-dialog`" show-button-bar show-clear fluid autofocus />
      </div>
      <p class="field-hint">{{ t('production.lots.requiredDeliveryDialog.hint') }}</p>
    </div>

    <template #footer>
      <Button
        :label="t('production.lots.requiredDeliveryDialog.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="visible = false"
      />
      <Button
        :label="t('production.lots.requiredDeliveryDialog.save')"
        :loading="submitting"
        @click="onSave"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.required-delivery-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-hint {
  margin: 0;
  font-weight: 400;
}
</style>
