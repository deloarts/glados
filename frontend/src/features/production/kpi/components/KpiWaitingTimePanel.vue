<script setup lang="ts">
// Median days between a predecessor position becoming ready and the next
// order's actual_start, grouped by the started order's own position kind.
// position_kind reuses production.lots.positionKind's existing translations
// rather than duplicating that enum's labels under a new namespace.
import { useI18n } from 'vue-i18n'

import { useKpiFormat } from '../composables/useKpiFormat'
import EmptyState from '@/shared/components/EmptyState.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'

import type { WaitingTimeRowResult } from '../types/productionKpiResponse'

defineProps<{
  rows: WaitingTimeRowResult[]
}>()

const { t } = useI18n()
const { formatDays } = useKpiFormat()

function positionKindLabel(kind: string): string {
  const key = `production.lots.positionKind.${kind}`
  const translated = t(key)
  return translated === key ? kind : translated
}
</script>

<template>
  <SectionCard :title="t('productionKpi.waitingTime.title')" flush fill>
    <template #title-end>
      <i
        class="mdi mdi-information-outline kpi-panel-info"
        aria-hidden="true"
        v-tooltip.top="t('productionKpi.definitions.waitingTime')"
      />
    </template>
    <DataTable :value="rows" size="small" data-key="position_kind">
      <Column :header="t('productionKpi.waitingTime.columns.positionKind')">
        <template #body="{ data }">{{
          positionKindLabel((data as WaitingTimeRowResult).position_kind)
        }}</template>
      </Column>
      <Column :header="t('productionKpi.waitingTime.columns.days')">
        <template #body="{ data }">{{
          formatDays((data as WaitingTimeRowResult).median_days)
        }}</template>
      </Column>
      <Column field="count" :header="t('productionKpi.waitingTime.columns.count')" />
      <template #empty>
        <EmptyState :message="t('productionKpi.waitingTime.empty')" />
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
