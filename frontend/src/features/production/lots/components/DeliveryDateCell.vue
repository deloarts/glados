<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { dateToParam as toDateParam } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import type { PlannedDateEditTarget } from '../../composables/useLotStepDeliveryInfo'

// The shared cell of the Planned Start and Planned Date columns; infoKey
// picks the field to show.
export interface PlannedStepInfo {
  date: Date | null
  // Shown with date so a multi-day job reads correctly. Null for a purely
  // external position.
  startDate: Date | null
  plannedByLabel: string | null
}

const props = defineProps<{
  info: PlannedStepInfo
  infoKey: 'date' | 'startDate'
  editTarget: PlannedDateEditTarget
}>()

const emit = defineEmits<{
  edit: [target: PlannedDateEditTarget]
}>()

const { t } = useI18n()
</script>

<template>
  <div class="delivery-cell">
    <span class="delivery-date-row">
      <span v-if="props.info[props.infoKey]">{{ toDateParam(props.info[props.infoKey]!) }}</span>
      <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      <Button
        v-if="editTarget"
        icon="mdi mdi-calendar-edit-outline"
        size="small"
        text
        rounded
        v-tooltip.top.focus="t('production.lots.plannedDate.edit')"
        :aria-label="t('production.lots.plannedDate.edit')"
        @click="emit('edit', editTarget)"
      />
    </span>
    <span v-if="info.plannedByLabel" class="delivery-note">{{ info.plannedByLabel }}</span>
  </div>
</template>

<style scoped lang="scss">
.delivery-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.delivery-date-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.delivery-note {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
