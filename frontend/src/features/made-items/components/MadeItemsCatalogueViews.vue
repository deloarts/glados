<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useMadeItemsCatalogueColumnsStore } from '../stores/madeItemsCatalogueColumnsStore'
import { useMadeItemsCatalogueFiltersStore } from '../stores/madeItemsCatalogueFiltersStore'
import {
  useMadeItemsCatalogueViewStore,
  useMadeItemsShowAllRevisionsStore,
} from '../stores/madeItemsCatalogueViewStore'
import { useMadeItemsStore } from '../stores/madeItemsStore'

import type { MadeItemColumnDefinition } from '../stores/madeItemsCatalogueColumnsStore'

const { t } = useI18n()

const columnsStore = useMadeItemsCatalogueColumnsStore()
const filtersStore = useMadeItemsCatalogueFiltersStore()
const viewStore = useMadeItemsCatalogueViewStore()
const showAllRevisionsStore = useMadeItemsShowAllRevisionsStore()
const madeItemsStore = useMadeItemsStore()

const columnsPopover = ref()

const visibleFields = computed<MadeItemColumnDefinition['field'][]>({
  get: () => columnsStore.visibleFields,
  set: (fields) => columnsStore.setVisibleFields(fields),
})

function toggleColumnsPopover(event: Event) {
  columnsPopover.value.toggle(event)
}

const sortByItems = computed(() => [
  {
    label: t('madeItems.catalogue.views.sortByItems.idDesc'),
    icon: 'mdi mdi-sort-numeric-descending',
    command: () => viewStore.setSort('id', 'desc'),
  },
  {
    label: t('madeItems.catalogue.views.sortByItems.idAsc'),
    icon: 'mdi mdi-sort-numeric-ascending',
    command: () => viewStore.setSort('id', 'asc'),
  },
  {
    label: t('madeItems.catalogue.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => viewStore.setSort('article_name', 'asc'),
  },
  {
    label: t('madeItems.catalogue.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => viewStore.setSort('article_name', 'desc'),
  },
  {
    label: t('madeItems.catalogue.views.sortByItems.changedDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => viewStore.setSort('changed', 'desc'),
  },
  {
    label: t('madeItems.catalogue.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => viewStore.setSort('created', 'desc'),
  },
])

const groupByItems = computed(() => [
  {
    label: t('madeItems.catalogue.views.groupByItems.category'),
    icon: 'mdi mdi-tag',
    command: () => viewStore.setGroupBy('article_groups'),
  },
])
</script>

<template>
  <ViewsBar
    id-prefix="made-items-catalogue"
    :show-actions="viewStore.showActions"
    :group-by-items="groupByItems"
    :group-by-active="!!viewStore.groupBy"
    :sort-by-items="sortByItems"
    :sort-by-active="!!viewStore.sortBy"
    :has-active-filters="filtersStore.hasActiveFilters"
    v-model:search="filtersStore.search"
    :search-placeholder="t('madeItems.catalogue.controls.search')"
    :show-archived="filtersStore.showArchived"
    @sync="madeItemsStore.triggerRefresh()"
    @toggle-show-actions="viewStore.toggleShowActions()"
    @clear-group-by="viewStore.clearGroupBy()"
    @clear-sort-by="viewStore.clearSort()"
    @clear="filtersStore.clearAll()"
    @toggle-show-archived="filtersStore.showArchived = !filtersStore.showArchived"
  >
    <template #start-extra>
      <Button
        :label="t('madeItems.catalogue.views.columns')"
        icon="mdi mdi-view-column-outline"
        severity="contrast"
        text
        @click="toggleColumnsPopover"
      />
      <Divider layout="vertical" />
      <Button
        :label="t('madeItems.catalogue.views.showAllRevisions')"
        icon="mdi mdi-filter-variant"
        severity="contrast"
        :text="!showAllRevisionsStore.showAllRevisions"
        @click="showAllRevisionsStore.toggleShowAllRevisions()"
      />
    </template>
  </ViewsBar>

  <Popover ref="columnsPopover">
    <MultiSelect
      v-model="visibleFields"
      :aria-label="t('madeItems.catalogue.views.columns')"
      :options="columnsStore.columns"
      option-label="header"
      option-value="field"
      data-key="field"
      display="chip"
      filter
      :placeholder="t('madeItems.catalogue.views.selectColumns')"
      style="min-width: 16rem"
    />
  </Popover>
</template>
