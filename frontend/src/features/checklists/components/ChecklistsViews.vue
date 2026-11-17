<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useChecklistsTableStores } from '../stores/checklistsTableStores'
import type { ChecklistGroupBy, ChecklistsContext } from '../stores/checklistsTableStores'
import type { ChecklistSortBy } from '../types/checklist'

/** Sync, Views, Group By, Sort By and Clear for a checklists table, like the catalogue's views bar. */

const props = defineProps<{
  context: ChecklistsContext
  /** The owner differs between rows; on a project's own tab it does not. */
  showOwner?: boolean
}>()

const { t } = useI18n()
const { view, filters } = useChecklistsTableStores(props.context)

const V = 'checklists.views'

const SORTS: { key: string; field: ChecklistSortBy; dir: 'asc' | 'desc'; icon: string }[] = [
  { key: 'changedDesc', field: 'changed', dir: 'desc', icon: 'mdi-sort-clock-descending' },
  { key: 'changedAsc', field: 'changed', dir: 'asc', icon: 'mdi-sort-clock-ascending' },
  { key: 'createdDesc', field: 'created', dir: 'desc', icon: 'mdi-sort-clock-descending' },
  { key: 'createdAsc', field: 'created', dir: 'asc', icon: 'mdi-sort-clock-ascending' },
  { key: 'numberDesc', field: 'number', dir: 'desc', icon: 'mdi-sort-numeric-descending' },
  { key: 'numberAsc', field: 'number', dir: 'asc', icon: 'mdi-sort-numeric-ascending' },
  { key: 'titleAsc', field: 'title', dir: 'asc', icon: 'mdi-sort-alphabetical-ascending' },
  { key: 'titleDesc', field: 'title', dir: 'desc', icon: 'mdi-sort-alphabetical-descending' },
  { key: 'typeAsc', field: 'type', dir: 'asc', icon: 'mdi-sort-alphabetical-ascending' },
  { key: 'verdictAsc', field: 'verdict', dir: 'asc', icon: 'mdi-sort-alphabetical-ascending' },
  { key: 'releasedDesc', field: 'released', dir: 'desc', icon: 'mdi-sort-clock-descending' },
]

const sortByItems = computed(() =>
  SORTS.map((sort) => ({
    label: t(`${V}.sortByItems.${sort.key}`),
    icon: `mdi ${sort.icon}`,
    command: () => view.setSort(sort.field, sort.dir),
  })),
)

const groups = computed<{ key: ChecklistGroupBy; icon: string }[]>(() => [
  { key: 'type', icon: 'mdi-clipboard-list-outline' },
  ...(props.showOwner ? [{ key: 'owner' as const, icon: 'mdi-folder-outline' }] : []),
  { key: 'verdict', icon: 'mdi-flag-outline' },
  { key: 'status', icon: 'mdi-check-decagram-outline' },
])

const groupByItems = computed(() =>
  groups.value.map((group) => ({
    label: t(`${V}.groupByItems.${group.key}`),
    icon: `mdi ${group.icon}`,
    command: () => view.setGroupBy(group.key),
  })),
)
</script>

<template>
  <ViewsBar
    :id-prefix="`checklists-${context}`"
    :show-actions="view.showActions"
    :group-by-items="groupByItems"
    :group-by-active="!!view.groupBy"
    :sort-by-items="sortByItems"
    :sort-by-active="!!view.sortBy"
    :has-active-filters="filters.hasActiveFilters"
    @sync="filters.triggerRefresh()"
    @toggle-show-actions="view.toggleShowActions()"
    @clear-group-by="view.clearGroupBy()"
    @clear-sort-by="view.clearSort()"
    @clear="filters.clearAll()"
  />
</template>
