<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useMachinePoolsStore } from '../stores/machinePoolsStore'

import type { MenuItem } from 'openvue/menuitem'

const { t } = useI18n()
const store = useMachinePoolsStore()
const { search, sortBy, showActions, hasActiveFilters, showArchived } = storeToRefs(store)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('productionMachinePools.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('name', 'asc'),
  },
  {
    label: t('productionMachinePools.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('name', 'desc'),
  },
  {
    label: t('productionMachinePools.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('productionMachinePools.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
])
</script>

<template>
  <ViewsBar
    id-prefix="machine-pools"
    :show-actions="showActions"
    :sort-by-items="sortByItems"
    :sort-by-active="!!sortBy"
    :has-active-filters="hasActiveFilters"
    :show-archived="showArchived"
    v-model:search="search"
    :search-placeholder="t('productionMachinePools.controls.search')"
    @sync="store.triggerRefresh()"
    @toggle-show-actions="store.toggleShowActions()"
    @clear-sort-by="store.clearSort()"
    @clear="store.clearAll()"
    @toggle-show-archived="store.toggleShowArchived()"
  />
</template>
