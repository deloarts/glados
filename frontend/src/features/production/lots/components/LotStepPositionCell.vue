<script setup lang="ts">
// Position cell of the lot step list, spanned across all steps of one
// position: its number, assignment kind and, for a grouped position, how
// many steps it holds.
import { useI18n } from 'vue-i18n'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import type { LotPositionResponse } from '../../types/productionLotsResponse'

defineProps<{
  position: LotPositionResponse | undefined
  stepCount: number
}>()

const { t } = useI18n()

const POSITION_KIND_ICON: Record<string, string> = {
  unassigned: 'mdi mdi-tray-full',
  external: 'mdi mdi-cart',
  internal: 'mdi mdi-factory',
  mixed: 'mdi mdi-swap-horizontal',
}
</script>

<template>
  <div class="position-cell">
    <span class="position-cell-label">
      <i :class="POSITION_KIND_ICON[position?.kind ?? 'unassigned'] ?? ''" aria-hidden="true" />
      {{ position ? `#${position.sequence}` : getEmptyPlaceholder() }}
    </span>
    <span class="position-cell-kind">{{
      position?.kind ? t(`production.lots.positionKind.${position.kind}`) : ''
    }}</span>
    <span v-if="stepCount > 1" class="position-cell-count">
      {{ t('production.lots.detail.steps.groupedStepCount', { count: stepCount }) }}
    </span>
  </div>
</template>

<style scoped lang="scss">
.position-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.position-cell-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: 700;
}

.position-cell-kind,
.position-cell-count {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
