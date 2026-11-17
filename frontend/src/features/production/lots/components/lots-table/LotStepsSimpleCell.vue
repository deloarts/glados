<script setup lang="ts">
import { inject } from 'vue'
import { useI18n } from 'vue-i18n'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { stepIcon } from '../../../utils/lotStepDisplay'
import { groupBreakdownTooltip, groupMethodLabel, positionGroups } from '../../utils/lotPositionGroups'
import { LOTS_TABLE_STEP_CONTEXT_KEY } from './lotsTableStepContext'

import type { LotSummaryResponse, LotSummaryStepResponse } from '../../../types/productionLotsResponse'

const props = defineProps<{
  lot: LotSummaryResponse
}>()

const { locale } = useI18n()
const ctx = inject(LOTS_TABLE_STEP_CONTEXT_KEY)!

function onTagClick(event: MouseEvent, primary: LotSummaryStepResponse): void {
  ctx.onStepClick(props.lot, primary, event)
}
</script>

<template>
  <div v-if="(lot.steps?.length ?? 0) > 0" class="steps-cell">
    <Tag
      v-for="group in positionGroups(lot)"
      :key="group.positionId"
      :value="
        group.steps.length > 1
          ? `${groupMethodLabel(group, locale)} (${group.steps.length})`
          : groupMethodLabel(group, locale)
      "
      :icon="stepIcon(group.primary)"
      :severity="ctx.stepSeverity(lot, group.primary)"
      class="step-tag"
      :class="{
        'step-tag--clickable': ctx.isStepClickable(lot, group.primary),
        'step-tag--selected': ctx.isStepSelected(lot, group.primary),
        'step-tag--resolving': ctx.isStepResolving(lot, group.primary),
      }"
      v-tooltip.top="groupBreakdownTooltip(group)"
      @click="onTagClick($event, group.primary)"
    />
  </div>
  <span v-else class="item-code">{{ getEmptyPlaceholder() }}</span>
</template>

<style scoped lang="scss">
.item-code {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.steps-cell {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.step-tag {
  font-size: var(--font-size-sm);
}

.step-tag--clickable {
  cursor: pointer;

  &:hover {
    opacity: 0.8;
  }
}

.step-tag--selected {
  outline: 2px solid var(--p-primary-color);
  outline-offset: 1px;
}

.step-tag--resolving {
  opacity: 0.5;
  pointer-events: none;
}
</style>
