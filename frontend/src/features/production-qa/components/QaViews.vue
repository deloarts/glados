<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useQaFiltersStore } from '../stores/qaFiltersStore'
import { useQaTasksStore } from '../stores/qaTasksStore'

import type { MenuItem } from 'openvue/menuitem'

const { t } = useI18n()
const filtersStore = useQaFiltersStore()
const tasksStore = useQaTasksStore()
const { search } = storeToRefs(filtersStore)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('productionQa.views.sortByItems.plannedAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => filtersStore.setSort('planned', 'asc'),
  },
  {
    label: t('productionQa.views.sortByItems.plannedDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => filtersStore.setSort('planned', 'desc'),
  },
  {
    label: t('productionQa.views.sortByItems.partAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => filtersStore.setSort('part', 'asc'),
  },
  {
    label: t('productionQa.views.sortByItems.lotAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => filtersStore.setSort('lot', 'asc'),
  },
])
</script>

<template>
  <ViewsBar
    id-prefix="production-qa"
    hide-views-toggle
    :syncing="tasksStore.refreshing"
    :sort-by-items="sortByItems"
    :sort-by-active="!!filtersStore.sortBy"
    :has-active-filters="filtersStore.hasActiveFilters"
    v-model:search="search"
    :search-placeholder="t('productionQa.views.searchPlaceholder')"
    @sync="tasksStore.refresh()"
    @clear-sort-by="filtersStore.clearSort()"
    @clear="filtersStore.clearAll()"
  >
    <!-- All three reveal work the default worklist hides, so all three are
         off by default and read as "filled = revealing". -->
    <template #extra>
      <Divider layout="vertical" />
      <Button
        :label="t('productionQa.views.showCompleted')"
        icon="mdi mdi-check-circle-outline"
        severity="contrast"
        :text="!filtersStore.showCompleted"
        v-tooltip.top="t('productionQa.views.showCompletedTooltip')"
        @click="filtersStore.showCompleted = !filtersStore.showCompleted"
      />
      <Button
        :label="t('productionQa.views.showCanceled')"
        icon="mdi mdi-close-circle-outline"
        severity="contrast"
        :text="!filtersStore.showCanceled"
        v-tooltip.top="t('productionQa.views.showCanceledTooltip')"
        @click="filtersStore.showCanceled = !filtersStore.showCanceled"
      />
      <Button
        :label="t('productionQa.views.showFuture')"
        icon="mdi mdi-clock-outline"
        severity="contrast"
        :text="!filtersStore.showFuture"
        v-tooltip.top="t('productionQa.views.showFutureTooltip')"
        @click="filtersStore.showFuture = !filtersStore.showFuture"
      />
    </template>
  </ViewsBar>
</template>
