<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useBoughtItemsCatalogueColumnsStore } from '../stores/boughtItemsCatalogueColumnsStore'
import { useBoughtItemsCatalogueFiltersStore } from '../stores/boughtItemsCatalogueFiltersStore'
import { useBoughtItemsCatalogueViewStore } from '../stores/boughtItemsCatalogueViewStore'
import { useBoughtItemsStore } from '../stores/boughtItemsStore'

import type { BoughtItemColumnDefinition } from '../stores/boughtItemsCatalogueColumnsStore'

const { t } = useI18n()

const columnsStore = useBoughtItemsCatalogueColumnsStore()
const filtersStore = useBoughtItemsCatalogueFiltersStore()
const viewStore = useBoughtItemsCatalogueViewStore()
const boughtItemsStore = useBoughtItemsStore()

const columnsPopover = ref()

const visibleFields = computed<BoughtItemColumnDefinition['field'][]>({
  get: () => columnsStore.visibleFields,
  set: (fields) => columnsStore.setVisibleFields(fields),
})

function toggleColumnsPopover(event: Event) {
  columnsPopover.value.toggle(event)
}

const sortByItems = computed(() => [
  {
    label: t('boughtItems.catalogue.views.sortByItems.idDesc'),
    icon: 'mdi mdi-sort-numeric-descending',
    command: () => viewStore.setSort('id', 'desc'),
  },
  {
    label: t('boughtItems.catalogue.views.sortByItems.idAsc'),
    icon: 'mdi mdi-sort-numeric-ascending',
    command: () => viewStore.setSort('id', 'asc'),
  },
  {
    label: t('boughtItems.catalogue.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => viewStore.setSort('article_name', 'asc'),
  },
  {
    label: t('boughtItems.catalogue.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => viewStore.setSort('article_name', 'desc'),
  },
  {
    label: t('boughtItems.catalogue.views.sortByItems.manufacturerAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => viewStore.setSort('manufacturer_name', 'asc'),
  },
  {
    label: t('boughtItems.catalogue.views.sortByItems.manufacturerDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => viewStore.setSort('manufacturer_name', 'desc'),
  },
  {
    label: t('boughtItems.catalogue.views.sortByItems.changedDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => viewStore.setSort('changed', 'desc'),
  },
  {
    label: t('boughtItems.catalogue.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => viewStore.setSort('created', 'desc'),
  },
])

const groupByItems = computed(() => [
  {
    label: t('boughtItems.catalogue.views.groupByItems.manufacturer'),
    icon: 'mdi mdi-cart',
    command: () => viewStore.setGroupBy('manufacturer_name'),
  },
  {
    label: t('boughtItems.catalogue.views.groupByItems.category'),
    icon: 'mdi mdi-tag',
    command: () => viewStore.setGroupBy('article_groups'),
  },
])
</script>

<template>
  <ViewsBar
    id-prefix="bought-items-catalogue"
    :show-actions="viewStore.showActions"
    :group-by-items="groupByItems"
    :group-by-active="!!viewStore.groupBy"
    :sort-by-items="sortByItems"
    :sort-by-active="!!viewStore.sortBy"
    :has-active-filters="filtersStore.hasActiveFilters"
    v-model:search="filtersStore.search"
    :search-placeholder="t('boughtItems.catalogue.controls.search')"
    :show-archived="filtersStore.showArchived"
    @sync="boughtItemsStore.triggerRefresh()"
    @toggle-show-actions="viewStore.toggleShowActions()"
    @clear-group-by="viewStore.clearGroupBy()"
    @clear-sort-by="viewStore.clearSort()"
    @clear="filtersStore.clearAll()"
    @toggle-show-archived="filtersStore.showArchived = !filtersStore.showArchived"
  >
    <template #start-extra>
      <Button
        :label="t('boughtItems.catalogue.views.columns')"
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
      :aria-label="t('boughtItems.catalogue.views.columns')"
      :options="columnsStore.columns"
      option-label="header"
      option-value="field"
      data-key="field"
      display="chip"
      filter
      :placeholder="t('boughtItems.catalogue.views.selectColumns')"
      style="min-width: 16rem"
    />
  </Popover>
</template>
