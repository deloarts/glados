<script setup lang="ts">
// Completions in period grouped by made item: completed, rejected, rework,
// scrap quantities and the resulting yield ratio.
import { useI18n } from 'vue-i18n'

import { useKpiFormat } from '../composables/useKpiFormat'
import EmptyState from '@/shared/components/EmptyState.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'

import type { QualityByItemRowResult } from '../types/productionKpiResponse'

defineProps<{
  rows: QualityByItemRowResult[]
}>()

const { t } = useI18n()
const { formatPercent, formatQuantity } = useKpiFormat()
</script>

<template>
  <SectionCard :title="t('productionKpi.qualityByItem.title')" flush fill>
    <DataTable :value="rows" size="small" data-key="made_item_id" scrollable scroll-height="flex">
      <Column :header="t('productionKpi.qualityByItem.columns.item')">
        <template #body="{ data }">
          <div class="item-cell">
            <span class="item-part-number">{{
              (data as QualityByItemRowResult).made_item_part_number
            }}</span>
            <span class="item-name">{{
              (data as QualityByItemRowResult).made_item_article_name
            }}</span>
          </div>
        </template>
      </Column>
      <Column :header="t('productionKpi.qualityByItem.columns.completed')">
        <template #body="{ data }">{{
          formatQuantity((data as QualityByItemRowResult).completed)
        }}</template>
      </Column>
      <Column :header="t('productionKpi.qualityByItem.columns.rejected')">
        <template #body="{ data }">{{
          formatQuantity((data as QualityByItemRowResult).rejected)
        }}</template>
      </Column>
      <Column :header="t('productionKpi.qualityByItem.columns.rework')">
        <template #body="{ data }">{{
          formatQuantity((data as QualityByItemRowResult).rework)
        }}</template>
      </Column>
      <Column :header="t('productionKpi.qualityByItem.columns.scrap')">
        <template #body="{ data }">{{
          formatQuantity((data as QualityByItemRowResult).scrap)
        }}</template>
      </Column>
      <Column :header="t('productionKpi.qualityByItem.columns.yield')">
        <template #body="{ data }">{{
          formatPercent((data as QualityByItemRowResult).yield_ratio.value)
        }}</template>
      </Column>
      <template #empty>
        <EmptyState :message="t('productionKpi.qualityByItem.empty')" />
      </template>
    </DataTable>
  </SectionCard>
</template>

<style scoped lang="scss">
.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.item-part-number {
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.item-name {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
