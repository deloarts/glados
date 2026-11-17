<script setup lang="ts">
// The side column of the order page: the note card over the extra costs
// card over the files card. The note is read-only here and edited through
// the controls bar; the files card takes the remaining height and scrolls.
import { useI18n } from 'vue-i18n'

import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import OrderExtraCostsCard from './OrderExtraCostsCard.vue'
import OrderFilesSection from './OrderFilesSection.vue'
import type { OrderResponse } from '../types/ordersResponse'

defineProps<{
  order: OrderResponse
  canWrite: boolean
  showFiles: boolean
}>()

const { t } = useI18n()
</script>

<template>
  <div class="side-panels">
    <SectionCard :title="t('orders.columns.note')" icon="mdi-note-text-outline" class="note-panel">
      <p v-if="order.note" class="note-text">{{ order.note }}</p>
      <p v-else class="note-empty">{{ t('orders.detail.noNoteSet') }}</p>
    </SectionCard>
    <OrderExtraCostsCard :order="order" class="extra-costs-panel" />
    <div v-if="showFiles" class="card files-panel">
      <OrderFilesSection :order="order" :can-write="canWrite" multi-layout="stack" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.side-panels {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.note-panel {
  flex: 0 0 auto;
  max-height: 12rem;
}

.note-text {
  margin: 0;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.note-empty {
  margin: 0;
  color: var(--p-text-muted-color);
  font-style: italic;
}

.extra-costs-panel {
  flex: 0 0 auto;
  max-height: 18rem;
}

.files-panel {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}
</style>
