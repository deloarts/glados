<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { AppLocale } from '@/core/i18n'
import { toDayKey } from '@/core/utils/dates'

import { useTickingNow } from '../../composables/useTickingNow'
import type { InfoscreenDeliveryRow, WidgetConfigOf, WidgetDataOf } from '../../types/infoscreenFeed'
import {
  daysBetween,
  formatDay,
  formatQuantity,
  joinParts,
  weekdayLabel,
} from '../../utils/infoscreenFormat'
import RowThumbnail from './RowThumbnail.vue'
import WidgetFrame from './WidgetFrame.vue'

// The deliveries grouped by day, as the feed sorts them: the overdue ones
// first when the screen asks for them, then today, tomorrow and the later
// days under their weekday. Today's group stands out, since that is what
// goods receipt prepares for.
const props = defineProps<{
  config: WidgetConfigOf<'deliveries_expected'>
  data: WidgetDataOf<'deliveries_expected'>
}>()

const { t, locale } = useI18n()
// The day turns over without a new feed, so the headings follow the clock.
const now = useTickingNow(60_000)

type DayGroup = {
  key: string
  label: string
  kind: 'overdue' | 'today' | 'later'
  rows: { row: InfoscreenDeliveryRow; index: number }[]
}

const groups = computed<DayGroup[]>(() => {
  const today = toDayKey(now.value.toISOString())
  const result: DayGroup[] = []
  props.data.deliveries.forEach((row, index) => {
    const offset = row.expected_date ? daysBetween(today, row.expected_date) : null
    let key: string
    let label: string
    let kind: DayGroup['kind'] = 'later'
    if (row.days_late !== null && row.days_late !== undefined) {
      key = 'overdue'
      label = t('infoscreenRuntime.widgets.deliveriesExpected.overdue')
      kind = 'overdue'
    } else if (offset === null || offset <= 0) {
      key = 'today'
      label = t('infoscreenRuntime.widgets.deliveriesExpected.today')
      kind = 'today'
    } else if (offset === 1) {
      key = 'tomorrow'
      label = t('infoscreenRuntime.widgets.deliveriesExpected.tomorrow')
    } else {
      key = row.expected_date ?? 'later'
      label = joinParts(
        weekdayLabel(row.expected_date ?? today, locale.value as AppLocale),
        formatDay(row.expected_date),
      )
    }
    const last = result[result.length - 1]
    if (last && last.key === key) last.rows.push({ row, index })
    else result.push({ key, label, kind, rows: [{ row, index }] })
  })
  return result
})

function rowKey(row: InfoscreenDeliveryRow, index: number): string {
  return `${row.order_number ?? ''}-${row.part_number ?? ''}-${index}`
}

function sideLabel(row: InfoscreenDeliveryRow): string | null {
  if (row.days_late) {
    return t('infoscreenRuntime.widgets.lateLots.daysLate', row.days_late)
  }
  return null
}
</script>

<template>
  <WidgetFrame
    :title="config.title || t('infoscreenRuntime.widgets.deliveriesExpected.title')"
    :count="data.deliveries.length"
  >
    <div v-if="data.deliveries.length > 0" class="delivery-groups">
      <section
        v-for="group in groups"
        :key="group.key"
        class="delivery-group"
        :class="`delivery-group--${group.kind}`"
        data-testid="delivery-group"
      >
        <h3 class="delivery-group-label">
          {{ group.label }}
          <span class="delivery-group-count">{{ group.rows.length }}</span>
        </h3>
        <ul class="delivery-rows">
          <li
            v-for="{ row, index } in group.rows"
            :key="rowKey(row, index)"
            class="delivery-row"
            data-testid="delivery-row"
          >
            <RowThumbnail :url="row.thumbnail_url" />
            <div class="delivery-row-main">
              <span class="delivery-row-item">{{ row.item_name ?? row.part_number }}</span>
              <span class="delivery-row-detail">
                {{ joinParts(row.part_number, row.order_number, row.supplier_name) }}
              </span>
            </div>
            <div class="delivery-row-side">
              <span class="delivery-row-quantity">{{ formatQuantity(row.quantity, row.unit) }}</span>
              <span v-if="sideLabel(row)" class="delivery-row-late">{{ sideLabel(row) }}</span>
            </div>
          </li>
        </ul>
      </section>
    </div>
    <p v-else class="widget-empty">
      {{ t('infoscreenRuntime.widgets.deliveriesExpected.empty') }}
    </p>
  </WidgetFrame>
</template>

<style scoped lang="scss">
.delivery-groups {
  display: flex;
  flex-direction: column;
  gap: 0.6em;
}

.delivery-group-label {
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

.delivery-group-count {
  font-variant-numeric: tabular-nums;
}

// Today's deliveries are what goods receipt prepares for, so they stand out.
.delivery-group--today {
  padding: 0.3em 0.6em;
  border-left: 0.3em solid var(--p-primary-color);
  border-radius: var(--p-border-radius-sm);
  background: color-mix(in srgb, var(--p-primary-color) 8%, transparent);

  .delivery-group-label {
    color: var(--p-primary-color);
  }
}

.delivery-group--overdue .delivery-group-label,
.delivery-row-late {
  color: var(--p-red-500);
}

.delivery-row-late {
  font-size: 0.8em;
  font-weight: 700;
}

.delivery-rows {
  list-style: none;
  margin: 0;
  padding: 0;
}

.delivery-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.35em 0;
  border-bottom: 1px solid var(--p-content-border-color);
}

.delivery-row-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.delivery-row-item {
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.delivery-row-detail {
  font-size: 0.8em;
  color: var(--p-text-muted-color);
}

.delivery-row-detail {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.delivery-row-side {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-variant-numeric: tabular-nums;
}

.widget-empty {
  margin: 0;
  color: var(--p-text-muted-color);
}
</style>
