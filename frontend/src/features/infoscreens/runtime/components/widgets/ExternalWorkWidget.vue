<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { AppLocale } from '@/core/i18n'
import { toDayKey } from '@/core/utils/dates'
import { formatUnit } from '@/shared/utils/units'

import { useTickingNow } from '../../composables/useTickingNow'
import type { WidgetConfigOf, WidgetDataOf } from '../../types/infoscreenFeed'
import {
  groupExternalWorkByDay,
  groupExternalWorkBySupplier,
  summarizeExternalWork,
} from '../../utils/externalWorkGroups'
import type { ExternalWorkDayGroup, ExternalWorkRow } from '../../utils/externalWorkGroups'
import { formatDay, formatQuantity, joinParts, weekdayLabel } from '../../utils/infoscreenFormat'
import RowThumbnail from './RowThumbnail.vue'
import WidgetFrame from './WidgetFrame.vue'

// What must leave the house for an outside process and by when, the
// outgoing counterpart of the expected deliveries. "days" groups the parts
// by their latest send-out day with today standing out; "suppliers" gives
// each supplier a lane with its next send-out day and how much of the
// batch is there already.
const props = defineProps<{
  config: WidgetConfigOf<'external_work'>
  data: WidgetDataOf<'external_work'>
}>()

const { t, locale } = useI18n()
// The day turns over without a new feed, so the groups follow the clock.
const now = useTickingNow(60_000)
const todayKey = computed(() => toDayKey(now.value.toISOString()))

const summary = computed(() => summarizeExternalWork(props.data.rows, todayKey.value))
const days = computed(() => groupExternalWorkByDay(props.data.rows, todayKey.value))
const lanes = computed(() => groupExternalWorkBySupplier(props.data.rows))

const KEY = 'infoscreenRuntime.widgets.externalWork'

function dayLabel(group: ExternalWorkDayGroup): string {
  if (group.kind !== 'later') return t(`${KEY}.${group.kind}`)
  return joinParts(weekdayLabel(group.date ?? todayKey.value, locale.value as AppLocale), formatDay(group.date))
}

function quantity(row: ExternalWorkRow): string | null {
  return formatQuantity(row.quantity, formatUnit('PCS'))
}

// Where the part goes: its methods, then the supplier.
function destination(row: ExternalWorkRow): string {
  const methods = row.methods.join(', ')
  if (!row.supplier_name) return methods
  return `${methods} → ${row.supplier_name}`
}

type Status = { kind: 'ready' | 'waiting' | 'late'; label: string }

function status(row: ExternalWorkRow): Status | null {
  if (row.alert === 'not_ready_in_time') return { kind: 'late', label: t(`${KEY}.notReadyInTime`) }
  if (row.ready_now) return { kind: 'ready', label: t(`${KEY}.ready`) }
  if (row.ready_from) {
    return {
      kind: 'waiting',
      label: t(`${KEY}.readyFrom`, {
        date: joinParts(weekdayLabel(row.ready_from, locale.value as AppLocale), formatDay(row.ready_from)),
      }),
    }
  }
  return null
}

function rowKey(row: ExternalWorkRow, index: number): string {
  return `${row.lot_number}-${row.part_number ?? ''}-${index}`
}

function isPast(day: string | null): boolean {
  return day !== null && day < todayKey.value
}

function readyShare(ready: number, total: number): string {
  return `${total === 0 ? 0 : Math.round((ready / total) * 100)}%`
}
</script>

<template>
  <WidgetFrame :title="config.title || t(`${KEY}.title`)" :count="data.rows.length">
    <div v-if="data.rows.length > 0" class="external-work">
      <p class="external-work-summary" data-testid="external-work-summary">
        <span>{{ t(`${KEY}.summaryToday`, { count: summary.today }) }}</span>
        <span>{{ t(`${KEY}.summaryWeek`, { count: summary.week }) }}</span>
        <span v-if="summary.critical > 0" class="external-work-critical">
          {{ t(`${KEY}.summaryCritical`, { count: summary.critical }) }}
        </span>
      </p>

      <div v-if="config.layout === 'suppliers'" class="external-work-lanes">
        <section
          v-for="lane in lanes"
          :key="lane.supplier ?? ''"
          class="external-work-lane"
          data-testid="external-work-lane"
        >
          <header class="lane-header">
            <h3 class="lane-supplier" :class="{ 'lane-supplier--suggested': lane.suggested }">
              {{ lane.supplier ?? t(`${KEY}.noSupplier`) }}
            </h3>
            <span
              v-if="lane.nextLatestPickup"
              class="lane-next"
              :class="{ 'lane-next--late': isPast(lane.nextLatestPickup) }"
            >
              {{ t(`${KEY}.nextSendOut`, { date: formatDay(lane.nextLatestPickup) }) }}
            </span>
          </header>
          <div
            class="lane-progress"
            role="progressbar"
            :aria-valuenow="lane.ready"
            :aria-valuemin="0"
            :aria-valuemax="lane.rows.length"
          >
            <span class="lane-progress-bar" :style="{ width: readyShare(lane.ready, lane.rows.length) }" />
          </div>
          <span class="lane-ready">
            {{ t(`${KEY}.readyOf`, { ready: lane.ready, total: lane.rows.length }) }}
          </span>
          <ul class="external-work-rows external-work-rows--compact">
            <li
              v-for="(row, index) in lane.rows"
              :key="rowKey(row, index)"
              class="external-work-row"
              data-testid="external-work-row"
            >
              <div class="row-main">
                <span class="row-item">{{ row.item_name ?? row.part_number }}</span>
                <span class="row-detail">{{ joinParts(row.lot_number, row.methods.join(', ')) }}</span>
              </div>
              <div class="row-side">
                <span :class="{ 'row-late': isPast(row.latest_pickup_date) }">
                  {{ formatDay(row.latest_pickup_date) }}
                </span>
                <span
                  v-if="status(row)"
                  class="row-status"
                  :class="`row-status--${status(row)?.kind}`"
                  >{{ status(row)?.label }}</span
                >
              </div>
            </li>
          </ul>
        </section>
      </div>

      <div v-else class="external-work-days">
        <section
          v-for="group in days"
          :key="group.key"
          class="external-work-day"
          :class="`external-work-day--${group.kind}`"
          data-testid="external-work-day"
        >
          <h3 class="day-label">
            {{ dayLabel(group) }}
            <span class="day-count">{{ group.rows.length }}</span>
          </h3>
          <ul class="external-work-rows">
            <li
              v-for="(row, index) in group.rows"
              :key="rowKey(row, index)"
              class="external-work-row"
              data-testid="external-work-row"
            >
              <RowThumbnail :url="row.thumbnail_url" />
              <div class="row-main">
                <span class="row-item">{{ row.item_name ?? row.part_number }}</span>
                <span class="row-detail">{{ joinParts(row.part_number, row.lot_number) }}</span>
                <span class="row-detail" :class="{ 'row-detail--suggested': row.supplier_suggested }">
                  {{ destination(row) }}
                </span>
              </div>
              <div class="row-side">
                <span class="row-quantity">{{ quantity(row) }}</span>
                <span v-if="row.alert === 'overdue' && row.days_late" class="row-late">
                  {{ t('infoscreenRuntime.widgets.lateLots.daysLate', row.days_late) }}
                </span>
                <span
                  v-if="status(row)"
                  class="row-status"
                  :class="`row-status--${status(row)?.kind}`"
                  >{{ status(row)?.label }}</span
                >
              </div>
            </li>
          </ul>
        </section>
      </div>
    </div>
    <p v-else class="widget-empty">{{ t(`${KEY}.empty`) }}</p>
  </WidgetFrame>
</template>

<style scoped lang="scss">
.external-work {
  display: flex;
  flex-direction: column;
  gap: 0.6em;
  min-height: 0;
}

.external-work-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4em 1.2em;
  margin: 0;
  font-size: 0.9em;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.external-work-critical,
.row-late,
.row-status--late,
.lane-next--late {
  color: var(--p-red-500);
}

.external-work-days {
  display: flex;
  flex-direction: column;
  gap: 0.6em;
}

.day-label {
  display: flex;
  align-items: baseline;
  gap: 0.5em;
  margin: 0;
  font-size: 0.75em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--p-text-muted-color);
}

.day-count {
  font-variant-numeric: tabular-nums;
}

// What must leave today is what shipping packs now, so it stands out.
.external-work-day--today {
  padding: 0.3em 0.6em;
  border-left: 0.3em solid var(--p-primary-color);
  border-radius: var(--p-border-radius-sm);
  background: color-mix(in srgb, var(--p-primary-color) 8%, transparent);

  .day-label {
    color: var(--p-primary-color);
  }
}

.external-work-day--overdue .day-label {
  color: var(--p-red-500);
}

.external-work-rows {
  list-style: none;
  margin: 0;
  padding: 0;
}

.external-work-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.35em 0;
  border-bottom: 1px solid var(--p-content-border-color);
}

.row-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.row-item {
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-detail {
  font-size: 0.8em;
  color: var(--p-text-muted-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

// A supplier that is only the method's default, not ordered yet.
.row-detail--suggested {
  font-style: italic;
}

.row-side {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-variant-numeric: tabular-nums;
}

.row-late,
.row-status {
  font-size: 0.8em;
  font-weight: 700;
}

.row-status--ready {
  color: var(--p-green-600);
}

.row-status--waiting {
  color: var(--p-text-muted-color);
}

.external-work-lanes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14em, 1fr));
  gap: 0.8em;
  align-items: start;
}

.external-work-lane {
  display: flex;
  flex-direction: column;
  gap: 0.35em;
  padding: 0.5em 0.7em;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
}

.lane-header {
  display: flex;
  flex-direction: column;
  gap: 0.1em;
}

.lane-supplier {
  margin: 0;
  font-size: 1em;
  font-weight: 700;
}

.lane-supplier--suggested {
  font-style: italic;
}

.lane-next {
  font-size: 0.8em;
  font-weight: 700;
  color: var(--p-primary-color);
}

.lane-progress {
  height: 0.45em;
  border-radius: 999px;
  background: var(--p-content-border-color);
  overflow: hidden;
}

.lane-progress-bar {
  display: block;
  height: 100%;
  background: var(--p-green-500);
}

.lane-ready {
  font-size: 0.8em;
  color: var(--p-text-muted-color);
  font-variant-numeric: tabular-nums;
}

.external-work-rows--compact .external-work-row {
  padding: 0.25em 0;
}

.widget-empty {
  margin: 0;
  color: var(--p-text-muted-color);
}
</style>
