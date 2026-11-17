<script setup lang="ts">
// Asks why a completion is reversed and books the reversal; the lot detail
// store reads the lot, its completions and its events again afterwards.
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { formatDecimal } from '@/core/utils/numbers'
import { productionErrorKey } from '../../../utils/productionErrors'
import { useProductionLotDetailStore } from '../../stores/productionLotDetailStore'

import type {
  ProductionOrderCompletionResponse,
  ProductionOrderResponse,
} from '../../../types/productionOrdersResponse'

const props = defineProps<{
  order: ProductionOrderResponse | null
  completion: ProductionOrderCompletionResponse | null
}>()

const visible = defineModel<boolean>('visible', { required: true })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const store = useProductionLotDetailStore()

const reason = ref('')
const saving = ref(false)
const errorMessage = ref<string | null>(null)

const canSave = computed(() => !!reason.value.trim() && !saving.value)

watch(visible, (open) => {
  if (open) {
    reason.value = ''
    errorMessage.value = null
  }
})

async function submit(): Promise<void> {
  if (!props.order || !props.completion || !reason.value.trim()) return
  saving.value = true
  errorMessage.value = null
  try {
    await store.reverseCompletion(props.order.id, props.completion.id, reason.value.trim())
    visible.value = false
  } catch (e) {
    const key = productionErrorKey(e)
    errorMessage.value = key ? t(key) : (extractApiError(e) ?? t('common.unexpectedError'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('production.lots.detail.record.execution.reverseTitle')"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <div class="reverse-body">
      <p v-if="completion" class="reverse-summary">
        {{ formatDecimal(completion.quantity) }} · {{ completion.completion_date }} ·
        {{ order?.production_order_number }}
      </p>
      <p class="reverse-hint">{{ t('production.lots.detail.record.execution.reverseHint') }}</p>
      <div class="field">
        <label :for="`${uid}-reverse-reason`">{{ t('production.lots.detail.record.execution.reverseReason') }} *</label>
        <Textarea v-model="reason" :id="`${uid}-reverse-reason`" rows="3" auto-resize fluid />
      </div>
      <Message v-if="errorMessage" severity="error" size="small" :closable="false">
        {{ errorMessage }}
      </Message>
    </div>
    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="saving"
        @click="visible = false"
      />
      <Button
        :label="t('production.lots.detail.record.execution.reverse')"
        severity="danger"
        :loading="saving"
        :disabled="!canSave"
        @click="submit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.reverse-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.reverse-summary {
  margin: 0;
  font-weight: 600;
}

.reverse-hint {
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}
</style>
