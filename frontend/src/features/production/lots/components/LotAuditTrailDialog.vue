<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatISODateTime } from '@/core/utils/dates'
import { useAppToast } from '@/core/composables/useAppToast'

import { extractApiError } from '@/core/utils/errors'
import { getLotEvents } from '../api/getLotEvents'
import LotAuditEventList from './lot-detail/LotAuditEventList.vue'

import type { LotEventResponse, LotSummaryResponse } from '../../types/productionLotsResponse'

const props = defineProps<{
  lot: LotSummaryResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const toast = useAppToast()

const events = ref<LotEventResponse[]>([])
const loading = ref(false)

// Self-contained (fetches by id) rather than reusing productionLotDetailStore:
// triggered from the lots list, which has no reason to open the shared
// lot-detail store's state just to show this one lot's history.
watch(
  () => [visible.value, props.lot?.id ?? null] as const,
  async ([isVisible, lotId]) => {
    if (!isVisible || lotId === null) return
    events.value = []
    loading.value = true
    try {
      events.value = await getLotEvents(lotId)
    } catch (e) {
      toast.error(t('production.lots.detail.audit.loadError'), extractApiError(e) ?? undefined)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    maximizable
    :header="lot?.lot_number ?? t('production.lots.detail.audit.title')"
    :style="{ width: 'var(--dialog-width-lg)' }"
    :content-style="{ maxHeight: '75vh', overflowY: 'auto' }"
  >
    <template v-if="lot">
      <div class="audit-source">
        <span class="field-label">{{ t('production.lots.detail.audit.source.title') }}</span>
        <div class="audit-source-row">
          <span>{{ lot.source_label || t('production.lots.detail.audit.source.noDemand') }}</span>
          <span v-if="lot.source_sublabel" class="item-code">{{ lot.source_sublabel }}</span>
        </div>
        <div v-if="lot.source_order_number" class="audit-source-row">
          <span>{{
            t('production.lots.detail.audit.source.order', { number: lot.source_order_number })
          }}</span>
          <span v-if="lot.source_delivery_date">
            {{ t('production.lots.detail.audit.source.actualDelivery') }}:
            {{ formatISODateTime(lot.source_delivery_date) }}
          </span>
          <span v-else-if="lot.source_expected_delivery_date">
            {{ t('production.lots.detail.audit.source.expectedDelivery') }}:
            {{ lot.source_expected_delivery_date }}
          </span>
        </div>
      </div>

      <Divider />
    </template>

    <LotAuditEventList
      :events="events"
      :loading="loading"
      :required-delivery-date="lot?.required_delivery_date ?? null"
    />
  </Dialog>
</template>

<style scoped lang="scss">
.audit-source {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-2);
}

.audit-source-row {
  display: flex;
  gap: var(--space-3);
  align-items: baseline;
  font-size: var(--font-size-sm);
}

.field-label {
  font-weight: 500;
}

.item-code {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
