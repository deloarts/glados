<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

defineProps<{
  lot: LotSummaryResponse
}>()

const { t } = useI18n()

// source_material is resolved server-side and only ever set when the lot is
// sourced from stock (a source item), since a bought/made-item source has no
// comparable material of its own, so those never flag a mismatch.
function hasMaterialMismatch(lot: LotSummaryResponse): boolean {
  const expected = lot.made_item_material
  const actual = lot.source_material
  if (!expected || !actual) return false
  return expected.trim().toLowerCase() !== actual.trim().toLowerCase()
}
</script>

<template>
  <div class="source-cell">
    <Tag
      v-if="lot.is_alteration"
      :value="t('production.lots.source.alteration')"
      severity="warn"
    />
    <template v-else-if="lot.source_label">
      <div class="source-info">
        <span class="source-label">{{ lot.source_label }}</span>
        <span v-if="lot.source_sublabel" class="source-sublabel">
          {{ lot.source_sublabel }}
        </span>
      </div>
      <i
        v-if="hasMaterialMismatch(lot)"
        class="mdi mdi-alert source-material-warning"
        v-tooltip.top="
          t('production.lots.source.materialMismatchTooltip', {
            expected: lot.made_item_material,
            actual: lot.source_material,
          })
        "
      />
    </template>
    <span v-else class="source-label">{{ getEmptyPlaceholder() }}</span>
  </div>
</template>

<style scoped lang="scss">
.source-cell {
  display: flex;
  align-items: center;
}

.source-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.source-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.source-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.source-material-warning {
  margin-left: var(--space-2);
  color: var(--p-orange-500);
  font-size: var(--font-size-sm);
}
</style>
