<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { useMadeItemLabel } from '@/features/made-items'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

const props = defineProps<{
  lot: LotSummaryResponse
  openDetailById: (id: number) => Promise<void>
}>()

const { t } = useI18n()
const { toastOnError } = useErrorToast()
const { format: madeItemLabel } = useMadeItemLabel()

function open(): void {
  props.openDetailById(props.lot.made_item_id).catch(toastOnError())
}
</script>

<template>
  <div class="item-cell">
    <span
      v-if="lot.made_item_part_number"
      class="item-name item-link"
      role="button"
      tabindex="0"
      @click.stop="open"
      @keydown.enter="open"
      >{{ madeItemLabel(lot.made_item_part_number, lot.made_item_revision) }}</span
    >
    <span v-else class="item-name-warning item-link" role="button" tabindex="0" @click.stop="open" @keydown.enter="open">
      <i class="mdi mdi-alert" aria-hidden="true" />
      {{ t('production.lots.noPartNumber') }}
    </span>
    <span class="item-code">{{ lot.made_item_article_name }}</span>
  </div>
</template>

<style scoped lang="scss">
.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
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

.item-name {
  font-size: var(--font-size-md);
  font-weight: 600;
}

.item-code {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.item-name-warning {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: 500;
  font-size: var(--font-size-sm);
  color: var(--p-orange-500);
}
</style>
