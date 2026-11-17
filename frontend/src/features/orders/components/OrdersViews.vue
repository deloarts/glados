<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useOrdersFiltersStore } from '../stores/ordersFiltersStore'
import { useOrdersStore } from '../stores/ordersStore'

import type { MenuItem } from 'openvue/menuitem'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const hostStore = useHostStore()
const filtersStore = useOrdersFiltersStore()
const ordersStore = useOrdersStore()
const { search, showActions, showOrderFiles, sortBy, groupBy } = storeToRefs(filtersStore)

const isTimelineOpen = computed(() => route.params.tab === 'timeline')

function toggleTimeline(): void {
  void router.push(isTimelineOpen.value ? '/procurement/orders' : '/procurement/orders/timeline')
}

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('orders.views.sortByItems.orderNumberDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => filtersStore.setSort('order_number', 'desc'),
  },
  {
    label: t('orders.views.sortByItems.orderNumberAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => filtersStore.setSort('order_number', 'asc'),
  },
  {
    label: t('orders.views.sortByItems.orderedDateDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => filtersStore.setSort('ordered_date', 'desc'),
  },
  {
    label: t('orders.views.sortByItems.orderedDateAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => filtersStore.setSort('ordered_date', 'asc'),
  },
  {
    label: t('orders.views.sortByItems.expectedDeliveryDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => filtersStore.setSort('expected_delivery_date', 'desc'),
  },
  {
    label: t('orders.views.sortByItems.expectedDeliveryAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => filtersStore.setSort('expected_delivery_date', 'asc'),
  },
])

const groupByItems = computed<MenuItem[]>(() => [
  {
    label: t('orders.views.groupByItems.status'),
    icon: 'mdi mdi-flag-outline',
    command: () => filtersStore.setGroupBy('status'),
  },
  {
    label: t('orders.views.groupByItems.supplier'),
    icon: 'mdi mdi-truck-outline',
    command: () => filtersStore.setGroupBy('supplier'),
  },
])
</script>

<template>
  <ViewsBar
    id-prefix="orders"
    :show-actions="showActions"
    :group-by-items="groupByItems"
    :group-by-active="!!groupBy"
    :sort-by-items="sortByItems"
    :sort-by-active="!!sortBy"
    :has-active-filters="filtersStore.hasActiveFilters"
    v-model:search="search"
    :search-placeholder="t('orders.filters.searchBy')"
    @sync="ordersStore.triggerRefresh()"
    @toggle-show-actions="filtersStore.toggleShowActions()"
    @clear-group-by="filtersStore.clearGroupBy()"
    @clear-sort-by="filtersStore.clearSort()"
    @clear="filtersStore.clearAll()"
  >
    <template #start-extra>
      <Button
        :label="
          isTimelineOpen ? t('orders.controls.closeTimeline') : t('orders.controls.openTimeline')
        "
        :icon="isTimelineOpen ? 'mdi mdi-format-list-bulleted' : 'mdi mdi-chart-gantt'"
        severity="contrast"
        :text="!isTimelineOpen"
        @click="toggleTimeline"
      />
    </template>
    <template #extra>
      <Divider layout="vertical" />
      <Button
        :label="t('orders.views.hideDelivered')"
        icon="mdi mdi-package-variant-closed-check"
        severity="contrast"
        :text="!filtersStore.hideDelivered"
        @click="filtersStore.toggleHideDelivered()"
      />
      <Button
        :label="t('orders.views.hideCanceled')"
        icon="mdi mdi-cancel"
        severity="contrast"
        :text="!filtersStore.hideCanceled"
        @click="filtersStore.toggleHideCanceled()"
      />
      <Button
        v-if="hostStore.storageEnabled"
        :label="t('orders.views.missingInvoice')"
        icon="mdi mdi-receipt-text-remove-outline"
        severity="contrast"
        :text="filtersStore.invoiceFilter !== 'missing'"
        @click="filtersStore.toggleMissingInvoice()"
      />
    </template>
    <template #popover-extra>
      <div class="views-toggle-item">
        <ToggleSwitch
          input-id="orders-files-toggle"
          :model-value="showOrderFiles"
          @update:model-value="filtersStore.toggleShowOrderFiles()"
        />
        <label for="orders-files-toggle">
          {{ t('orders.views.showFiles') }}
        </label>
      </div>
    </template>
  </ViewsBar>
</template>

<style lang="css" scoped>
.views-toggle-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  label {
    cursor: pointer;
  }
}
</style>
