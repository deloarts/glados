<script setup lang="ts">
// Where the period's bookings do not yet carry what planning will read from
// them: orders that ran through hours without working time, final
// completions without an assessment, and manual pauses without a cause.
// One table lists every finding, worst first within each kind.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import EmptyState from '@/shared/components/EmptyState.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'

import type { ProductionKpiBookingQualityResult } from '../types/productionKpiResponse'

const props = defineProps<{
  result: ProductionKpiBookingQualityResult | null
}>()

const { t } = useI18n()

type FindingKind = 'outside' | 'missing' | 'uncaused'

interface FindingRow {
  key: string
  kind: FindingKind
  orderNumber: string
  lotNumber: string
  detail: string
}

const rows = computed<FindingRow[]>(() => {
  const result = props.result
  if (!result) return []
  return [
    ...result.outside_working_time.map((r) => ({
      key: `outside-${r.order_id}`,
      kind: 'outside' as const,
      orderNumber: r.production_order_number,
      lotNumber: r.lot_number,
      detail: t('productionKpi.bookingQuality.details.outside', {
        minutes: r.outside_minutes,
        booked: r.booked_minutes,
      }),
    })),
    ...result.missing_assessments.map((r) => ({
      key: `missing-${r.order_id}`,
      kind: 'missing' as const,
      orderNumber: r.production_order_number,
      lotNumber: r.lot_number,
      detail: t('productionKpi.bookingQuality.details.completedAt', {
        date: formatISODateTime(r.completed_at),
      }),
    })),
    ...result.uncaused_pauses.map((r, index) => ({
      key: `uncaused-${r.order_id}-${index}`,
      kind: 'uncaused' as const,
      orderNumber: r.production_order_number,
      lotNumber: r.lot_number,
      detail: t('productionKpi.bookingQuality.details.pausedAt', {
        date: formatISODateTime(r.paused_at),
      }),
    })),
  ]
})

const summary = computed(() => {
  const result = props.result
  if (!result) return []
  return [
    t('productionKpi.bookingQuality.summary.outside', {
      count: result.outside_working_time.length,
      total: result.orders_with_bookings,
    }),
    t('productionKpi.bookingQuality.summary.missing', {
      count: result.missing_assessments.length,
      total: result.final_completions,
    }),
    t('productionKpi.bookingQuality.summary.uncaused', {
      count: result.uncaused_pauses.length,
      total: result.manual_pauses,
      since: formatISODateTime(result.booking_quality_since),
    }),
  ]
})
</script>

<template>
  <SectionCard :title="t('productionKpi.bookingQuality.title')" flush fill>
    <template #title-end>
      <i
        class="mdi mdi-information-outline kpi-panel-info"
        aria-hidden="true"
        v-tooltip.top="t('productionKpi.definitions.bookingQuality')"
      />
    </template>
    <ul v-if="summary.length" class="booking-quality-summary">
      <li v-for="line in summary" :key="line">{{ line }}</li>
    </ul>
    <DataTable :value="rows" size="small" data-key="key">
      <Column :header="t('productionKpi.bookingQuality.columns.finding')">
        <template #body="{ data }">{{
          t(`productionKpi.bookingQuality.kinds.${(data as FindingRow).kind}`)
        }}</template>
      </Column>
      <Column field="orderNumber" :header="t('productionKpi.bookingQuality.columns.order')" />
      <Column field="lotNumber" :header="t('productionKpi.bookingQuality.columns.lot')" />
      <Column field="detail" :header="t('productionKpi.bookingQuality.columns.detail')" />
      <template #empty>
        <EmptyState :message="t('productionKpi.bookingQuality.empty')" />
      </template>
    </DataTable>
  </SectionCard>
</template>

<style scoped lang="scss">
.kpi-panel-info {
  color: var(--p-text-muted-color);
  cursor: help;
}

.booking-quality-summary {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  list-style: none;
}
</style>
