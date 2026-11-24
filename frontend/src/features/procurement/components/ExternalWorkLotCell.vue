<script setup lang="ts">
// The lot column of the external work list: the lot, which opens its
// detail, and below it the project and the product, which open their pages.
import { useLotDetail } from '@/shared/composables/useLotDetail'

import type { ExternalWorkRow } from '../types/externalWork'

defineProps<{
  row: ExternalWorkRow
}>()

const { openLotDetail } = useLotDetail()
</script>

<template>
  <div class="cell-stack">
    <a
      class="link strong"
      role="button"
      tabindex="0"
      @click.stop="openLotDetail(row.lot_id)"
      @keydown.enter.stop="openLotDetail(row.lot_id)"
      >{{ row.lot_number }}</a
    >
    <span class="muted">
      <RouterLink class="link" :to="`/workspace/projects/${row.project_id}`" @click.stop>{{
        row.project_number
      }}</RouterLink
      ><template v-if="row.product_id !== null">
        ·
        <RouterLink class="link" :to="`/workspace/products/${row.product_id}`" @click.stop>{{
          row.product_number
        }}</RouterLink></template
      >
    </span>
  </div>
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
