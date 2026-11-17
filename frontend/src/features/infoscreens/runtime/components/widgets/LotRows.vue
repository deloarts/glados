<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { InfoscreenLotRow } from '../../types/infoscreenFeed'
import { formatDay, joinParts, statusLabel } from '../../utils/infoscreenFormat'
import RowThumbnail from './RowThumbnail.vue'

// The rows of the two lot widgets: the lot number first, then what it makes,
// and the target date on the right. An overdue lot, which both widgets
// list, shows how late it is in red instead, with a red edge on the row
// so it stands out from across the hall. The customer shows
// only when the widget asks for it, and the feed leaves it out otherwise.
const props = defineProps<{
  lots: InfoscreenLotRow[]
  showCustomer: boolean
}>()

function isLate(lot: InfoscreenLotRow): boolean {
  return lot.days_late !== null && lot.days_late > 0
}

const { t, te } = useI18n()

function detail(lot: InfoscreenLotRow): string {
  return joinParts(
    lot.part_number,
    lot.item_name,
    lot.project_number,
    props.showCustomer ? lot.customer_name : null,
  )
}
</script>

<template>
  <ul class="lot-rows">
    <li
      v-for="lot in lots"
      :key="lot.lot_id"
      class="lot-row"
      :class="{ 'lot-row--late': isLate(lot) }"
      data-testid="lot-row"
    >
      <RowThumbnail :url="lot.thumbnail_url" />
      <div class="lot-row-main">
        <span class="lot-row-number">{{ lot.lot_number }}</span>
        <span class="lot-row-detail">{{ detail(lot) }}</span>
      </div>
      <div class="lot-row-side">
        <span v-if="isLate(lot)" class="lot-row-late" data-testid="lot-row-late">
          {{ t('infoscreenRuntime.widgets.lateLots.daysLate', lot.days_late ?? 0) }}
        </span>
        <span v-else-if="lot.target_date" class="lot-row-date">
          {{ formatDay(lot.target_date) }}
        </span>
        <span class="lot-row-status">
          {{ statusLabel(t, te, lot.status, ['production.lots.status']) }}
        </span>
      </div>
    </li>
  </ul>
</template>

<style scoped lang="scss">
.lot-rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.lot-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.35em 0;
  border-bottom: 1px solid var(--p-content-border-color);
}

.lot-row--late {
  padding-left: 0.4em;
  border-left: 0.25em solid var(--p-red-500);
}

.lot-row-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.lot-row-number {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.lot-row-detail,
.lot-row-status {
  color: var(--p-text-muted-color);
  font-size: 0.8em;
}

.lot-row-detail {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lot-row-side {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  text-align: right;
}

.lot-row-date {
  font-variant-numeric: tabular-nums;
}

.lot-row-late {
  font-weight: 700;
  color: var(--p-red-500);
}
</style>
