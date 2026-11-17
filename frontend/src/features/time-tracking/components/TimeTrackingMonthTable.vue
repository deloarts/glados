<script setup lang="ts">
// One row per day of the month, as the time tracking system reports it.
// Weekends and holidays are muted, today is highlighted, negative balances
// show in the danger colour, and a day's single bookings fold out from the
// bookings column. Today's row arrives with live figures from the view.
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatISODate, formatISOTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { formatDuration, formatSignedDuration } from '@/shared/utils/formatDuration'
import { shortWeekdayName } from '../utils/timeTrackingMonth'
import type { TimeTrackingDay, TimeTrackingDayStatus } from '../types/timeTrackingTypes'

defineProps<{
  days: TimeTrackingDay[]
  todayDate: string | null
}>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const expandedRows = ref<Record<string, boolean>>({})

const STATUS_SEVERITY: Record<TimeTrackingDayStatus, string> = {
  normal: 'success',
  shift_free: 'secondary',
  holiday: 'info',
  absence: 'contrast',
  open: 'warn',
}

function statusLabel(status: TimeTrackingDayStatus): string {
  return t(`timeTracking.dayStatus.${status}`)
}

function statusSeverity(status: TimeTrackingDayStatus): string {
  return STATUS_SEVERITY[status]
}

function rowClass(day: TimeTrackingDay, todayDate: string | null): string[] {
  const classes: string[] = []
  if (day.weekday >= 6 || day.status === 'holiday') classes.push('tt-row--muted')
  if (day.date === todayDate) classes.push('tt-row--today')
  return classes
}

function timeOrDash(iso: string | null): string {
  return iso ? formatISOTime(iso) : getEmptyPlaceholder()
}

function durationOrDash(seconds: number | null): string {
  return seconds === null ? getEmptyPlaceholder() : formatDuration(seconds)
}

function balanceOrDash(seconds: number | null): string {
  return seconds === null ? getEmptyPlaceholder() : formatSignedDuration(seconds)
}

function negative(seconds: number | null): boolean {
  return seconds !== null && seconds <= -60
}

function toggle(date: string): void {
  const next = { ...expandedRows.value }
  if (next[date]) delete next[date]
  else next[date] = true
  expandedRows.value = next
}
</script>

<template>
  <div class="card tt-card" data-testid="time-tracking-month-table">
    <DataTable
      :value="days"
      data-key="date"
      v-model:expanded-rows="expandedRows"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      :row-class="(row: TimeTrackingDay) => rowClass(row, todayDate)"
    >
      <template #empty>
        <EmptyState :message="t('timeTracking.table.empty')" icon="mdi mdi-calendar-blank-outline" />
      </template>

      <Column :header="t('timeTracking.table.date')">
        <template #body="{ data }">
          <span class="tt-date">
            <span class="tt-weekday">{{ shortWeekdayName((data as TimeTrackingDay).weekday) }}</span>
            {{ formatISODate((data as TimeTrackingDay).date) }}
          </span>
        </template>
      </Column>
      <Column :header="t('timeTracking.table.shift')">
        <template #body="{ data }">
          <span :title="(data as TimeTrackingDay).shift_name ?? undefined">
            {{ (data as TimeTrackingDay).shift_short_name ?? getEmptyPlaceholder() }}
          </span>
        </template>
      </Column>
      <Column :header="t('timeTracking.table.firstIn')" body-class="tt-num">
        <template #body="{ data }">{{ timeOrDash((data as TimeTrackingDay).first_in) }}</template>
      </Column>
      <Column :header="t('timeTracking.table.lastOut')" body-class="tt-num">
        <template #body="{ data }">{{ timeOrDash((data as TimeTrackingDay).last_out) }}</template>
      </Column>
      <Column :header="t('timeTracking.table.bookings')">
        <template #body="{ data }">
          <Button
            v-if="(data as TimeTrackingDay).bookings.length > 0"
            :label="String((data as TimeTrackingDay).bookings.length)"
            :icon="expandedRows[(data as TimeTrackingDay).date] ? 'mdi mdi-chevron-up' : 'mdi mdi-chevron-down'"
            icon-pos="right"
            severity="secondary"
            text
            size="small"
            :aria-expanded="!!expandedRows[(data as TimeTrackingDay).date]"
            :aria-label="t('timeTracking.table.showBookings')"
            :data-testid="`time-tracking-bookings-${(data as TimeTrackingDay).date}`"
            @click="toggle((data as TimeTrackingDay).date)"
          />
          <span v-else class="tt-muted">{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>
      <Column :header="t('timeTracking.table.worked')" body-class="tt-num">
        <template #body="{ data }">{{ durationOrDash((data as TimeTrackingDay).worked_seconds) }}</template>
      </Column>
      <Column :header="t('timeTracking.table.target')" body-class="tt-num">
        <template #body="{ data }">{{ formatDuration((data as TimeTrackingDay).target_seconds) }}</template>
      </Column>
      <Column :header="t('timeTracking.table.dayBalance')" body-class="tt-num">
        <template #body="{ data }">
          <span :class="{ 'is-negative': negative((data as TimeTrackingDay).day_balance_seconds) }">
            {{ balanceOrDash((data as TimeTrackingDay).day_balance_seconds) }}
          </span>
        </template>
      </Column>
      <Column :header="t('timeTracking.table.runningBalance')" body-class="tt-num">
        <template #body="{ data }">
          <span :class="{ 'is-negative': negative((data as TimeTrackingDay).running_balance_seconds) }">
            {{ balanceOrDash((data as TimeTrackingDay).running_balance_seconds) }}
          </span>
        </template>
      </Column>
      <Column :header="t('timeTracking.table.status')">
        <template #body="{ data }">
          <Tag
            :value="statusLabel((data as TimeTrackingDay).status)"
            :severity="statusSeverity((data as TimeTrackingDay).status)"
          />
        </template>
      </Column>

      <template #expansion="{ data }">
        <ul class="tt-bookings" :data-testid="`time-tracking-booking-list-${(data as TimeTrackingDay).date}`">
          <li v-for="booking in (data as TimeTrackingDay).bookings" :key="booking.at">
            <i
              :class="booking.direction === 'in' ? 'mdi mdi-login' : 'mdi mdi-logout'"
              aria-hidden="true"
            />
            {{ formatISOTime(booking.at) }}
            <span class="tt-muted">{{
              booking.direction === 'in' ? t('timeTracking.table.in') : t('timeTracking.table.out')
            }}</span>
          </li>
        </ul>
      </template>
    </DataTable>
  </div>
</template>

<style scoped lang="scss">
.tt-card {
  padding: var(--space-2);
  height: auto;
}

.tt-date {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.tt-weekday {
  display: inline-block;
  min-width: 2.25rem;
  color: var(--p-text-muted-color);
}

.tt-muted {
  color: var(--p-text-muted-color);
}

.is-negative {
  color: var(--p-red-500);
}

:deep(.tt-num) {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

:deep(.tt-row--muted) {
  color: var(--p-text-muted-color);
}

:deep(.tt-row--today) > td {
  background: color-mix(in srgb, var(--p-primary-500) 10%, transparent);
  font-weight: 600;
}

.tt-bookings {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  margin: 0;
  padding: var(--space-1) var(--space-2);
  list-style: none;

  li {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    font-variant-numeric: tabular-nums;
  }
}
</style>
