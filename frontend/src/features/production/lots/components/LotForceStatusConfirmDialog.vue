<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { getLot } from '../../api/getLot'

import type { LotResponse } from '../../types/productionLotsResponse'

const props = defineProps<{
  visible: boolean
  lotId: number | null
  action: 'complete' | 'cancel'
  // Pre-loaded lot; when omitted the lot is fetched on open for the cascade
  // counts.
  lot?: LotResponse | null
  // True while the parent's mutation is in flight.
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:visible': [boolean]
  confirm: [reason: string | null]
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const loading = ref(false)
const resolvedLot = ref<LotResponse | null>(null)
const reason = ref('')

watch(
  () => [props.visible, props.lotId, props.lot] as const,
  async ([visible, lotId, lot]) => {
    if (!visible || lotId === null) return
    reason.value = ''
    if (lot) {
      resolvedLot.value = lot
      return
    }
    resolvedLot.value = null
    loading.value = true
    try {
      resolvedLot.value = await getLot(lotId)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

// Non-terminal orders the cascade will cancel or complete.
const liveOrderCount = computed(() => {
  if (!resolvedLot.value) return 0
  let count = 0
  for (const position of resolvedLot.value.positions ?? []) {
    for (const order of position.production_orders ?? []) {
      if (order.status !== 'completed' && order.status !== 'canceled') count++
    }
  }
  return count
})

// Positions with an undelivered order item the cascade will cancel, close
// short or, on a cancel, leave open for purchasing.
const liveOrderItemCount = computed(() => {
  if (!resolvedLot.value) return 0
  return (resolvedLot.value.positions ?? []).filter(
    (p) => p.order_item_id != null && p.order_item_status !== 'delivered',
  ).length
})

// Two independent plurals, so each count gets its own phrase inside the
// sentence.
const ordersPhrase = computed(() =>
  t('production.lots.detail.forceStatus.inProgressOrdersPhrase', liveOrderCount.value),
)
const itemsPhrase = computed(() =>
  t('production.lots.detail.forceStatus.orderItemsPhrase', liveOrderItemCount.value),
)

function close(): void {
  emit('update:visible', false)
}

function onConfirm(): void {
  emit('confirm', reason.value.trim() || null)
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-sm)' }"
    :header="t(`production.lots.detail.forceStatus.${action}.title`)"
    @update:visible="close"
  >
    <p class="warning-text">
      {{
        t(`production.lots.detail.forceStatus.${action}.warning`, {
          ordersPhrase,
          itemsPhrase,
        })
      }}
    </p>

    <div class="field">
      <label :for="`${uid}-reason`">{{ t('production.lots.detail.forceStatus.reason') }}</label>
      <Textarea v-model="reason" :id="`${uid}-reason`" rows="3" auto-resize fluid />
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="close"
      />
      <Button
        :label="t(`production.lots.detail.forceStatus.${action}.confirm`)"
        :severity="action === 'cancel' ? 'danger' : 'success'"
        :loading="loading || Boolean(submitting)"
        @click="onConfirm"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.warning-text {
  margin: 0 0 var(--space-4);
  font-size: var(--font-size-sm);
}

.field {
  label {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }
}
</style>
