<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useLotDetail } from '@/shared/composables/useLotDetail'
import { useMadeItemLabel } from '@/features/made-items'

import type { OrderItemResponse } from '../../types/ordersResponse'

defineProps<{ item: OrderItemResponse }>()

const emit = defineEmits<{
  openItem: [id: number]
}>()

const { t } = useI18n()
// A documented module-scope singleton (see useLotDetail.ts). Safe to call
// directly, unlike useBoughtItemDetail/useMadeItemDetail which create a
// fresh ref per call and whose mounted dialog the parent owns.
const { openLotDetail } = useLotDetail()
const { format: madeItemLabel } = useMadeItemLabel()
</script>

<template>
  <div class="item-cell">
    <span
      v-if="item.made_item_id !== null && item.item_part_number"
      class="item-name item-link"
      role="button"
      tabindex="0"
      @click.stop="emit('openItem', item.made_item_id!)"
      @keydown.enter="emit('openItem', item.made_item_id!)"
      >{{ madeItemLabel(item.item_part_number, item.item_revision) }}</span
    >
    <span v-else-if="item.item_part_number" class="item-name">{{
      madeItemLabel(item.item_part_number, item.item_revision)
    }}</span>
    <span v-else class="item-name-warning">
      <i class="mdi mdi-alert" aria-hidden="true" />
      {{ t('orders.items.noPartNumber') }}
    </span>
    <span v-if="item.item_article_name" class="item-code">{{ item.item_article_name }}</span>
    <a
      v-if="item.lot_number && item.lot_id"
      class="lot-number-badge lot-number-link"
      role="button"
      tabindex="0"
      @click.stop="openLotDetail(item.lot_id!)"
      @keydown.enter.stop="openLotDetail(item.lot_id!)"
    >
      {{ item.lot_number }} ({{ item.fabrication_method }})
    </a>
  </div>
</template>

<style scoped lang="scss">
.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 10rem;
}

.item-name {
  font-weight: 600;
}

.item-name-warning {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: 500;
  font-size: var(--font-size-sm);
  color: var(--p-orange-500);
}

.item-link {
  cursor: pointer;
  color: inherit;
  width: fit-content;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.item-code {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}

.lot-number-badge {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}

.lot-number-link {
  text-decoration: none;
  width: fit-content;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}
</style>
