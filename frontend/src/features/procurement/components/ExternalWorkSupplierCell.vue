<script setup lang="ts">
// The supplier column of the external work list: the line's supplier in
// bold with its order below, or the method's default supplier marked as a
// suggestion. The supplier opens its dialog, the order its detail.
import { useI18n } from 'vue-i18n'

import type { ExternalWorkRow } from '../types/externalWork'

defineProps<{
  row: ExternalWorkRow
}>()

const emit = defineEmits<{
  'open-supplier': [row: ExternalWorkRow]
  'open-order': [row: ExternalWorkRow]
}>()

const { t } = useI18n()
</script>

<template>
  <div v-if="row.order_item_id !== null" class="cell-stack">
    <a
      class="link strong"
      role="button"
      tabindex="0"
      @click.stop="emit('open-supplier', row)"
      @keydown.enter.stop="emit('open-supplier', row)"
      >{{ row.supplier_name }}</a
    >
    <a
      class="link muted"
      role="button"
      tabindex="0"
      data-testid="external-work-order-link"
      @click.stop="emit('open-order', row)"
      @keydown.enter.stop="emit('open-order', row)"
      >{{ row.order_number }}</a
    >
  </div>
  <span v-else-if="row.suggested_supplier_name" class="suggestion">
    <a
      class="link muted"
      role="button"
      tabindex="0"
      @click.stop="emit('open-supplier', row)"
      @keydown.enter.stop="emit('open-supplier', row)"
      >{{ row.suggested_supplier_name }}</a
    >
    <Tag severity="secondary" :value="t('procurement.externalWork.suggestion')" />
  </span>
  <span v-else class="muted">—</span>
</template>

<style scoped lang="scss">
.cell-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.strong {
  font-weight: 600;
}

.muted {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}

.suggestion {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.link {
  color: inherit;
  text-decoration: none;
  cursor: pointer;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}
</style>
