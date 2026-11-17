<script setup lang="ts">
// Open lots whose projected end already exceeds their target date, sorted
// most-late first by the backend. This is a point-in-time state, not a
// period aggregate (see getProductionKpiLateLots's docstring), so the
// period filter narrows nothing here, only machine/pool/project/customer do.
import { useI18n } from 'vue-i18n'

import { formatISODate } from '@/core/utils/dates'
import EmptyState from '@/shared/components/EmptyState.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'

import type { LateLotResult } from '../types/productionKpiResponse'

defineProps<{
  rows: LateLotResult[]
}>()

const { t } = useI18n()

function driverLabel(row: LateLotResult): string {
  if (row.driver_reason === null) return t('productionKpi.lateLots.noDriver')
  return t(`productionKpi.lateLots.driverReasons.${row.driver_reason}`)
}
</script>

<template>
  <SectionCard :title="t('productionKpi.lateLots.title')" flush fill>
    <DataTable :value="rows" size="small" data-key="lot_id" scrollable scroll-height="flex">
      <Column :header="t('productionKpi.lateLots.columns.lot')">
        <template #body="{ data }">
          <RouterLink
            class="lot-link"
            :to="`/production/lots/${(data as LateLotResult).lot_id}`"
            >{{ (data as LateLotResult).lot_number }}</RouterLink
          >
        </template>
      </Column>
      <Column :header="t('productionKpi.lateLots.columns.targetDate')">
        <template #body="{ data }">{{
          formatISODate((data as LateLotResult).target_date)
        }}</template>
      </Column>
      <Column :header="t('productionKpi.lateLots.columns.projectedEnd')">
        <template #body="{ data }">{{
          formatISODate((data as LateLotResult).projected_end)
        }}</template>
      </Column>
      <Column field="days_late" :header="t('productionKpi.lateLots.columns.daysLate')" />
      <Column :header="t('productionKpi.lateLots.columns.driver')">
        <template #body="{ data }">{{ driverLabel(data as LateLotResult) }}</template>
      </Column>
      <template #empty>
        <EmptyState :message="t('productionKpi.lateLots.empty')" icon="mdi mdi-check-circle-outline" />
      </template>
    </DataTable>
  </SectionCard>
</template>

<style scoped lang="scss">
.lot-link {
  color: var(--p-primary-color);
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}
</style>
