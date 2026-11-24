<script setup lang="ts">
// The header of a group in the external work list: the method or supplier,
// how many rows the group has on this page, the next latest pickup still
// open, in red once it has passed, and how many rows are critical.
import { useI18n } from 'vue-i18n'

import { formatDateOrDash, todayKey } from '@/core/utils/dates'

import type { ExternalWorkGroupSummary } from '../utils/externalWork'
import type { ExternalWorkGroupBy } from '../types/externalWork'

defineProps<{
  label: string
  groupBy: ExternalWorkGroupBy
  summary: ExternalWorkGroupSummary
}>()

const { t } = useI18n()
const today = todayKey()
</script>

<template>
  <div class="group-header" data-testid="external-work-group">
    <i
      :class="groupBy === 'method' ? 'mdi mdi-cog-outline' : 'mdi mdi-truck-outline'"
      aria-hidden="true"
    />
    <span class="group-header-label">{{ label }}</span>
    <Tag
      severity="secondary"
      :value="t('procurement.externalWork.group.positions', { count: summary.count }, summary.count)"
    />
    <Tag
      v-if="summary.nextLatestPickup"
      :severity="summary.nextLatestPickup < today ? 'danger' : 'info'"
      :value="
        t('procurement.externalWork.group.nextLatestPickup', {
          date: formatDateOrDash(summary.nextLatestPickup),
        })
      "
    />
    <Tag
      v-if="summary.critical > 0"
      severity="danger"
      :value="t('procurement.externalWork.group.critical', { count: summary.critical })"
    />
  </div>
</template>

<style scoped lang="scss">
.group-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.group-header-label {
  font-weight: bold;
}
</style>
