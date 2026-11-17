<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useSourceItemsCatalogueColumnsStore } from '../stores/sourceItemsCatalogueColumnsStore'
import { useSourceItemsCatalogueFiltersStore } from '../stores/sourceItemsCatalogueFiltersStore'
import { useSourceItemsCatalogueViewStore } from '../stores/sourceItemsCatalogueViewStore'
import { useSourceItemsStore } from '../stores/sourceItemsStore'

import type { SourceItemColumnDefinition } from '../stores/sourceItemsCatalogueColumnsStore'

const { t } = useI18n()

const columnsStore = useSourceItemsCatalogueColumnsStore()
const filtersStore = useSourceItemsCatalogueFiltersStore()
const viewStore = useSourceItemsCatalogueViewStore()
const sourceItemsStore = useSourceItemsStore()

const columnsPopover = ref()

const visibleFields = computed<SourceItemColumnDefinition['field'][]>({
  get: () => columnsStore.visibleFields,
  set: (fields) => columnsStore.setVisibleFields(fields),
})

function toggleColumnsPopover(event: Event) {
  columnsPopover.value.toggle(event)
}

const sortByItems = computed(() => [
  {
    label: t('sourceItems.catalogue.views.sortByItems.idDesc'),
    icon: 'mdi mdi-sort-numeric-descending',
    command: () => viewStore.setSort('id', 'desc'),
  },
  {
    label: t('sourceItems.catalogue.views.sortByItems.idAsc'),
    icon: 'mdi mdi-sort-numeric-ascending',
    command: () => viewStore.setSort('id', 'asc'),
  },
  {
    label: t('sourceItems.catalogue.views.sortByItems.changedDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => viewStore.setSort('changed', 'desc'),
  },
  {
    label: t('sourceItems.catalogue.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => viewStore.setSort('created', 'desc'),
  },
])

const groupByItems = computed(() => [
  {
    label: t('sourceItems.catalogue.views.groupByItems.manufacturer'),
    icon: 'mdi mdi-cart',
    command: () => viewStore.setGroupBy('manufacturer_name'),
  },
  {
    label: t('sourceItems.catalogue.views.groupByItems.status'),
    icon: 'mdi mdi-tag',
    command: () => viewStore.setGroupBy('status'),
  },
])
</script>

<template>
  <ViewsBar
    id-prefix="source-items-catalogue"
    :show-actions="viewStore.showActions"
    :group-by-items="groupByItems"
    :group-by-active="!!viewStore.groupBy"
    :sort-by-items="sortByItems"
    :sort-by-active="!!viewStore.sortBy"
    :has-active-filters="filtersStore.hasActiveFilters"
    v-model:search="filtersStore.search"
    :search-placeholder="t('sourceItems.catalogue.controls.search')"
    :show-archived="filtersStore.showArchived"
    @sync="sourceItemsStore.triggerRefresh()"
    @toggle-show-actions="viewStore.toggleShowActions()"
    @clear-group-by="viewStore.clearGroupBy()"
    @clear-sort-by="viewStore.clearSort()"
    @clear="filtersStore.clearAll()"
    @toggle-show-archived="filtersStore.showArchived = !filtersStore.showArchived"
  >
    <template #start-extra>
      <Button
        :label="t('sourceItems.catalogue.views.columns')"
        icon="mdi mdi-view-column-outline"
        severity="contrast"
        text
        @click="toggleColumnsPopover"
      />
    </template>
  </ViewsBar>

  <Popover ref="columnsPopover">
    <MultiSelect
      v-model="visibleFields"
      :aria-label="t('sourceItems.catalogue.views.columns')"
      :options="columnsStore.columns"
      option-label="header"
      option-value="field"
      data-key="field"
      display="chip"
      filter
      :placeholder="t('sourceItems.catalogue.views.selectColumns')"
      style="min-width: 16rem"
    />
  </Popover>
</template>
