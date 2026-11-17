<script setup lang="ts">
import { formatDateOrDash, formatDateTimeOrEmpty } from '@/core/utils/dates'

import WeekTag from '../WeekTag.vue'

// The plain date-with-tooltip cell shared by Ordered/Expected/Delivery/
// Created. The week tag only makes sense next to a date someone might act
// on (Ordered, Delivery), not next to a record's own creation timestamp.
defineProps<{
  date: string | null
  showWeekTag?: boolean
}>()
</script>

<template>
  <div v-if="showWeekTag" class="date-cell">
    <span :title="formatDateTimeOrEmpty(date)">{{ formatDateOrDash(date) }}</span>
    <WeekTag :date="date" />
  </div>
  <span v-else :title="formatDateTimeOrEmpty(date)">{{ formatDateOrDash(date) }}</span>
</template>

<style scoped lang="scss">
.date-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  white-space: nowrap;
}
</style>
