<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { BoughtItemSelect } from '@/features/bought-items'

import type { BoughtItemResponse } from '@/features/bought-items'

// `itemLocked` once the line received goods, which keep the item they came as.
defineProps<{ originalItemId: number | null; itemLocked?: boolean }>()

const virtualName = defineModel<string>('virtualName', { default: '' })
const selectedItem = defineModel<BoughtItemResponse | null>('selectedItem', { default: null })
const substituteReason = defineModel<string>('substituteReason', { default: '' })

const { t } = useI18n()
</script>

<template>
  <div class="edit-item-cell">
    <InputText
      class="cell-control"
      v-if="!selectedItem"
      v-model="virtualName"
      :placeholder="t('orders.items.edit.virtualNamePlaceholder')"
      size="small"
    />
    <BoughtItemSelect
      class="cell-control"
      v-model="selectedItem"
      :aria-label="t('orders.items.edit.substituteCataloguePlaceholder')"
      :placeholder="t('orders.items.edit.substituteCataloguePlaceholder')"
      :disabled="itemLocked"
      show-clear
      size="small"
    />
    <InputText
      class="cell-control"
      v-if="selectedItem && selectedItem.id !== originalItemId"
      v-model="substituteReason"
      :placeholder="t('orders.items.edit.substituteReasonPlaceholder')"
      size="small"
    />
  </div>
</template>

<style scoped lang="scss">
.edit-item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  :deep(.cell-control) {
    min-width: 16rem;
  }
}
</style>
