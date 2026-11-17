<script setup lang="ts">
import { computed, ref } from 'vue'
import { FilterMatchMode } from '@openvue/core/api'
import { useI18n } from 'vue-i18n'

import { useOrderFormatters } from '@/features/orders'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatPercent } from '@/core/utils/currency'
import EmptyState from '@/shared/components/EmptyState.vue'
import type { ProjectSummaryResponse } from '@/features/projects'

const props = defineProps<{
  summary: ProjectSummaryResponse | null
}>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { formatPrice } = useOrderFormatters()

const costsWithShare = computed(() => {
  const total = props.summary?.total_ordered_cost ?? 0
  return (props.summary?.cost_by_supplier ?? []).map((v) => ({
    ...v,
    share: formatPercent(total > 0 ? v.ordered_cost / total : null),
  }))
})

const costsFilters = ref({
  supplier_name: { value: null, matchMode: FilterMatchMode.CONTAINS },
})
</script>

<template>
  <DataTable
    :value="costsWithShare"
    v-model:filters="costsFilters"
    filter-display="row"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    scrollable
    scroll-height="flex"
    table-style="width: auto"
    resizable-columns
    column-resize-mode="expand"
  >
    <template #empty>
      <EmptyState :message="t('resources.projects.detail.costs.empty')" />
    </template>
    <Column header="#" style="width: 3rem" body-class="row-number" :show-filter-menu="false">
      <template #body="{ index }">{{ index + 1 }}</template>
      <template #filter />
    </Column>
    <Column
      field="supplier_name"
      :header="t('resources.projects.detail.costs.supplier')"
      sortable
      :show-filter-menu="false"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.detail.costs.supplier') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      :header="t('resources.projects.detail.costs.orderedCost')"
      sortable
      style="width: 12rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }">{{ formatPrice(data.ordered_cost) }}</template>
      <template #filter />
    </Column>
    <Column
      :header="t('resources.projects.detail.costs.deliveredCost')"
      sortable
      style="width: 12rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }">{{ formatPrice(data.delivered_cost) }}</template>
      <template #filter />
    </Column>
    <Column
      field="share"
      :header="t('resources.projects.detail.costs.share')"
      style="width: 8rem"
      :show-filter-menu="false"
    >
      <template #filter />
    </Column>
    <Column style="width: 100%"></Column>
  </DataTable>
</template>
