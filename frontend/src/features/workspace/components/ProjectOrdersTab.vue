<script setup lang="ts">
import { computed, ref } from 'vue'
import { FilterMatchMode } from '@openvue/core/api'
import { useI18n } from 'vue-i18n'

import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { formatISODate } from '@/core/utils/dates'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useClipboard } from '@/core/composables/useClipboard'
import { useOrderFormatters } from '@/features/orders'
import type { OrderResponse } from '@/features/orders'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'

/**
 * The orders that hold items for a project, or for any project of a
 * product, with what those items cost. Items of other projects on the same
 * order are left out of that cost.
 */

interface ProjectOrder {
  order: OrderResponse
  projectCost: number | null
}

const props = defineProps<{
  orders: OrderResponse[]
  /** The project, or all projects of the product, whose items count towards the cost. */
  projectIds: number[]
  /** Header of the cost column. */
  costLabel: string
}>()

const { t } = useI18n()
const { copyToClipboard } = useClipboard()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { formatPrice, orderStatusSeverity } = useOrderFormatters()

const projectOrders = computed<ProjectOrder[]>(() => {
  const projectIds = new Set(props.projectIds)
  return props.orders.map((o) => {
    const projectItems = (o.items ?? []).filter(
      (i) => i.project_id !== null && projectIds.has(i.project_id) && i.price !== null,
    )
    const cost = projectItems.length
      ? Math.round(projectItems.reduce((sum, i) => sum + i.price! * i.quantity, 0))
      : null
    return { order: o, projectCost: cost }
  })
})

const ordersFilters = ref({
  'order.order_number': { value: null, matchMode: FilterMatchMode.CONTAINS },
  'order.supplier_name': { value: null, matchMode: FilterMatchMode.CONTAINS },
})

const cm = ref()
const contextMenuItem = ref<ProjectOrder | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const row = contextMenuItem.value
  if (!row) return []

  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(row.order.public_id),
    },
  ]
})
</script>

<template>
  <DataTable
    :value="projectOrders"
    v-model:filters="ordersFilters"
    v-model:context-menu-selection="contextMenuItem"
    filter-display="row"
    data-key="order.id"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    scrollable
    scroll-height="flex"
    table-style="width: auto"
    resizable-columns
    column-resize-mode="expand"
    @row-contextmenu="onRowContextMenu"
  >
    <template #empty>
      <EmptyState :message="t('resources.projects.detail.orders.empty')" />
    </template>
    <Column header="#" style="width: 3rem" body-class="row-number" :show-filter-menu="false">
      <template #body="{ index }">{{ index + 1 }}</template>
      <template #filter />
    </Column>
    <Column
      field="order.order_number"
      :header="t('orders.columns.orderNumber')"
      sortable
      style="width: 10rem"
      :show-filter-menu="false"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('orders.columns.orderNumber') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column :header="t('orders.columns.status')" style="width: 10rem" :show-filter-menu="false">
      <template #body="{ data }: { data: ProjectOrder }">
        <Tag
          :value="t('orders.status.' + data.order.status)"
          :severity="orderStatusSeverity(data.order.status)"
        />
      </template>
      <template #filter />
    </Column>
    <Column
      field="order.supplier_name"
      :header="t('orders.columns.supplier')"
      sortable
      :show-filter-menu="false"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('orders.columns.supplier') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      :header="costLabel"
      style="width: 10rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: ProjectOrder }">
        {{ data.projectCost !== null ? formatPrice(data.projectCost) : getEmptyPlaceholder() }}
      </template>
      <template #filter />
    </Column>
    <Column :header="t('orders.columns.created')" style="width: 8rem" :show-filter-menu="false">
      <template #body="{ data }: { data: ProjectOrder }">
        {{ formatISODate(data.order.created) }}
      </template>
      <template #filter />
    </Column>
    <Column style="width: 100%"></Column>
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
</template>
