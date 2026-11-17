<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { BucketsMenu } from '@/features/buckets'
import { useBoughtItemsDemandsFiltersStore } from '../stores/boughtItemsDemandsFiltersStore'
import { useBoughtItemsProcurementStore } from '../stores/boughtItemsProcurementStore'
import { useBoughtItemsDemandsStore } from '@/features/bought-items'

const { t } = useI18n()
const filtersStore = useBoughtItemsDemandsFiltersStore()
const demandsStore = useBoughtItemsDemandsStore()
const procurementStore = useBoughtItemsProcurementStore()

// Some selected ids can fall outside the current (filtered/paginated) list,
// surfaced as "(K hidden)" next to the selection count rather than silently
// dropped, so a batch action still visibly covers rows the user can't see
// right now.
const hiddenSelectedCount = computed(() => {
  const visibleIds = new Set(demandsStore.items.map((d) => d.id))
  return procurementStore.selectedDemands.filter((d) => !visibleIds.has(d.id)).length
})

const sortByItems = computed(() => [
  {
    label: t('boughtItems.demands.views.sortByItems.idDesc'),
    icon: 'mdi mdi-sort-numeric-descending',
    command: () => filtersStore.setSort('id', 'desc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.idAsc'),
    icon: 'mdi mdi-sort-numeric-ascending',
    command: () => filtersStore.setSort('id', 'asc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => filtersStore.setSort('article_name', 'asc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => filtersStore.setSort('article_name', 'desc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.manufacturerAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => filtersStore.setSort('manufacturer_name', 'asc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.manufacturerDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => filtersStore.setSort('manufacturer_name', 'desc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.desiredDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => filtersStore.setSort('desired_delivery_date', 'desc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.desiredAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => filtersStore.setSort('desired_delivery_date', 'asc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => filtersStore.setSort('created', 'desc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.bucketAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => filtersStore.setSort('bucket_name', 'asc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.bucketDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => filtersStore.setSort('bucket_name', 'desc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.projectAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => filtersStore.setSort('project_number', 'asc'),
  },
  {
    label: t('boughtItems.demands.views.sortByItems.projectDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => filtersStore.setSort('project_number', 'desc'),
  },
])

const groupByItems = computed(() => [
  {
    label: t('boughtItems.demands.views.groupByItems.status'),
    icon: 'mdi mdi-flag-outline',
    command: () => filtersStore.setGroupBy('status'),
  },
  {
    label: t('boughtItems.demands.views.groupByItems.project'),
    icon: 'mdi mdi-folder-outline',
    command: () => filtersStore.setGroupBy('project'),
  },
  {
    label: t('boughtItems.demands.views.groupByItems.manufacturer'),
    icon: 'mdi mdi-cart',
    command: () => filtersStore.setGroupBy('manufacturer'),
  },
  {
    label: t('boughtItems.demands.views.groupByItems.bucket'),
    icon: 'mdi mdi-bucket-outline',
    command: () => filtersStore.setGroupBy('bucket'),
  },
])
</script>

<template>
  <ViewsBar
    id-prefix="bought-items-demands"
    :show-actions="filtersStore.showActions"
    :group-by-items="groupByItems"
    :group-by-active="!!filtersStore.groupBy"
    :sort-by-items="sortByItems"
    :sort-by-active="!!filtersStore.sortBy"
    :has-active-filters="filtersStore.hasActiveFilters"
    v-model:search="filtersStore.search"
    :search-placeholder="t('boughtItems.demands.controls.search')"
    @sync="demandsStore.triggerRefresh()"
    @toggle-show-actions="filtersStore.toggleShowActions()"
    @clear-group-by="filtersStore.clearGroupBy()"
    @clear-sort-by="filtersStore.clearSort()"
    @clear="filtersStore.clearAll()"
  >
    <template #extra>
      <BucketsMenu
        resource-type="bought_item_demand"
        v-model:bucket-ids="filtersStore.bucketIds"
        v-model:include-unbucketed="filtersStore.includeUnbucketed"
        @deleted="demandsStore.triggerRefresh()"
      />
      <Divider layout="vertical" />
      <Button
        :label="t('boughtItems.demands.views.showFulfilled')"
        icon="mdi mdi-check-circle-outline"
        severity="contrast"
        :text="!filtersStore.showFulfilled"
        @click="filtersStore.showFulfilled = !filtersStore.showFulfilled"
      />
      <Button
        :label="t('boughtItems.demands.views.showCanceled')"
        icon="mdi mdi-close-circle-outline"
        severity="contrast"
        :text="!filtersStore.showCanceled"
        @click="filtersStore.showCanceled = !filtersStore.showCanceled"
      />
    </template>
    <template v-if="procurementStore.selectedDemands.length > 0" #end>
      <Tag
        :value="
          hiddenSelectedCount > 0
            ? `${t('boughtItems.demands.views.selection.count', { count: procurementStore.selectedDemands.length })} ${t('boughtItems.demands.views.selection.hidden', { count: hiddenSelectedCount })}`
            : t('boughtItems.demands.views.selection.count', {
                count: procurementStore.selectedDemands.length,
              })
        "
        severity="secondary"
      />
      <Button
        :label="t('boughtItems.demands.views.selection.clear')"
        text
        size="small"
        severity="secondary"
        @click="procurementStore.clearSelection()"
      />
    </template>
  </ViewsBar>
</template>
