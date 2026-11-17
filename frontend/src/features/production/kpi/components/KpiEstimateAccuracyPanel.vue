<script setup lang="ts">
// Median (net work minutes / estimated_duration_minutes) per fabrication
// method: a value above 100% means the job typically ran longer than
// estimated, below means the estimate was pessimistic.
import { useI18n } from 'vue-i18n'

import { useKpiFormat } from '../composables/useKpiFormat'
import EmptyState from '@/shared/components/EmptyState.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'

import type { EstimateAccuracyRowResult } from '../types/productionKpiResponse'
import { localizeLabel } from '@/shared/utils/localizeLabel'

defineProps<{
  rows: EstimateAccuracyRowResult[]
}>()

const { t } = useI18n()
const { formatPercent } = useKpiFormat()
</script>

<template>
  <SectionCard :title="t('productionKpi.estimateAccuracy.title')" flush fill>
    <template #title-end>
      <i
        class="mdi mdi-information-outline kpi-panel-info"
        aria-hidden="true"
        v-tooltip.top="t('productionKpi.definitions.estimateAccuracy')"
      />
    </template>
    <DataTable :value="rows" size="small" data-key="fabrication_method_id">
      <Column
        field="fabrication_method_name"
        :header="t('productionKpi.estimateAccuracy.columns.method')"
      >
        <template #body="{ data }">{{ localizeLabel(data.fabrication_method_name) }}</template>
      </Column>
      <Column :header="t('productionKpi.estimateAccuracy.columns.ratio')">
        <template #body="{ data }">{{
          formatPercent((data as EstimateAccuracyRowResult).median_ratio)
        }}</template>
      </Column>
      <Column field="count" :header="t('productionKpi.estimateAccuracy.columns.count')" />
      <template #empty>
        <EmptyState :message="t('productionKpi.estimateAccuracy.empty')" />
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
