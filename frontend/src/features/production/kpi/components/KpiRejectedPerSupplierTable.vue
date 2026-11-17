<script setup lang="ts">
// Rejected-at-receipt volume per supplier: delivered and rejected
// quantity, the rejected ratio over everything received, and how much
// of the rejected quantity was lost for good rather than re-delivered.
import { useI18n } from 'vue-i18n'

import { useKpiFormat } from '../composables/useKpiFormat'
import EmptyState from '@/shared/components/EmptyState.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'

import type { RejectedPerSupplierRowResult } from '../types/productionKpiResponse'

defineProps<{
  rows: RejectedPerSupplierRowResult[]
}>()

const { t } = useI18n()
const { formatPercent, formatQuantity } = useKpiFormat()
</script>

<template>
  <SectionCard :title="t('productionKpi.rejectedPerSupplier.title')" flush fill>
    <template #title-end>
      <i
        class="mdi mdi-information-outline kpi-panel-info"
        aria-hidden="true"
        v-tooltip.top="t('productionKpi.definitions.rejectedPerSupplier')"
      />
    </template>
    <DataTable :value="rows" size="small" data-key="supplier_id" scrollable scroll-height="flex">
      <Column
        field="supplier_name"
        :header="t('productionKpi.rejectedPerSupplier.columns.supplier')"
      />
      <Column :header="t('productionKpi.rejectedPerSupplier.columns.delivered')">
        <template #body="{ data }">{{
          formatQuantity((data as RejectedPerSupplierRowResult).delivered)
        }}</template>
      </Column>
      <Column :header="t('productionKpi.rejectedPerSupplier.columns.rejected')">
        <template #body="{ data }">{{
          formatQuantity((data as RejectedPerSupplierRowResult).rejected)
        }}</template>
      </Column>
      <Column :header="t('productionKpi.rejectedPerSupplier.columns.ratio')">
        <template #body="{ data }">{{
          formatPercent((data as RejectedPerSupplierRowResult).rejected_ratio.value)
        }}</template>
      </Column>
      <Column :header="t('productionKpi.rejectedPerSupplier.columns.lost')">
        <template #body="{ data }">{{
          formatQuantity((data as RejectedPerSupplierRowResult).rejected_lost)
        }}</template>
      </Column>
      <template #empty>
        <EmptyState :message="t('productionKpi.rejectedPerSupplier.empty')" />
      </template>
    </DataTable>
  </SectionCard>
</template>

<style scoped lang="scss">
.kpi-panel-info {
  color: var(--p-text-muted-color);
  cursor: help;
}
</style>
