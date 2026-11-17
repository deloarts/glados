<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useProductionMachinesStore } from '../stores/productionMachinesStore'

import type { MenuItem } from 'openvue/menuitem'

const { t } = useI18n()
const store = useProductionMachinesStore()
const { search, sortBy, groupBy, showActions, hasActiveFilters, showArchived } = storeToRefs(store)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('productionMachines.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('internal_name', 'asc'),
  },
  {
    label: t('productionMachines.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('internal_name', 'desc'),
  },
  {
    label: t('productionMachines.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('productionMachines.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
])

const groupByItems = computed<MenuItem[]>(() => [
  {
    label: t('productionMachines.views.groupByItems.capability'),
    icon: 'mdi mdi-cog-outline',
    command: () => store.setGroupBy('capability'),
  },
])
</script>

<template>
  <ViewsBar
    id-prefix="production-machines"
    :show-actions="showActions"
    :group-by-items="groupByItems"
    :group-by-active="!!groupBy"
    :sort-by-items="sortByItems"
    :sort-by-active="!!sortBy"
    :has-active-filters="hasActiveFilters"
    :show-archived="showArchived"
    v-model:search="search"
    :search-placeholder="t('productionMachines.controls.search')"
    @sync="store.triggerRefresh()"
    @toggle-show-actions="store.toggleShowActions()"
    @clear-group-by="store.clearGroupBy()"
    @clear-sort-by="store.clearSort()"
    @clear="store.clearAll()"
    @toggle-show-archived="store.toggleShowArchived()"
  />
</template>
