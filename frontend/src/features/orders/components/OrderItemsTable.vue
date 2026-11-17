<script setup lang="ts">
// Items of one order as a table, used as the expansion row under the orders
// list and as the content of the order detail page. Rows are edited inline,
// and every row action is reachable from the context menu and the row's
// overflow button.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { formatDateOrDash, formatDateTimeOrEmpty } from '@/core/utils/dates'
import { currencyInputPrefix } from '@/core/utils/currency'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import {
  BoughtItemDetailDialog,
  BoughtItemThumbnailCell,
  useBoughtItemDetail,
} from '@/features/bought-items'
import { MadeItemDetailDialog, MadeItemThumbnailCell, useMadeItemDetail } from '@/features/made-items'
import ProjectSelect from '@/shared/components/project/ProjectSelect.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import DemandDateRangeFilter from '@/shared/components/demands/DemandDateRangeFilter.vue'
import NumberRangeRowFilter from '@/shared/components/table-filters/NumberRangeRowFilter.vue'
import { disabledItemTooltipPt as menuPt } from '@/shared/utils/menuItemTooltip'
import { useOrdersStore } from '../stores/ordersStore'
import { useOrderFormatters } from '../composables/useOrderFormatters'
import { useOrderItemInlineEdit } from '../composables/useOrderItemInlineEdit'
import { useOrderItemRows } from '../composables/useOrderItemRows'
import { useOrderItemRowMenus } from '../composables/useOrderItemRowMenus'
import { orderItemActionGates } from '../composables/useOrderItemActions'
import ConfirmActionDialog from '@/shared/components/dialogs/ConfirmActionDialog.vue'
import OrderItemActionsCell from './OrderItemActionsCell.vue'
import OrderItemQuantityCell from './OrderItemQuantityCell.vue'
import OrderItemQuantityEdit from './OrderItemQuantityEdit.vue'
import OrderItemProjectCell from './OrderItemProjectCell.vue'
import OrderItemPickupCell from './OrderItemPickupCell.vue'
import OrderItemTextFilter from './OrderItemTextFilter.vue'
import OrderItemCellView from './order-item-cell/OrderItemCellView.vue'
import OrderItemCellMadeEdit from './order-item-cell/OrderItemCellMadeEdit.vue'
import OrderItemCellSourceEdit from './order-item-cell/OrderItemCellSourceEdit.vue'
import OrderItemCellBoughtEdit from './order-item-cell/OrderItemCellBoughtEdit.vue'
import OrderItemCellVirtualEdit from './order-item-cell/OrderItemCellVirtualEdit.vue'

import type { OrderItemResponse, OrderResponse } from '../types/ordersResponse'

const props = withDefaults(
  defineProps<{
    order: OrderResponse
    canWrite: boolean
    canManage?: boolean
    /** receive:deliveries, which gates the deliver action alone. */
    canReceiveDeliveries?: boolean
    search?: string
    /**
     * `embedded` is the expansion row under the orders list: unsorted, since
     * position order is meaningful, and without filters. `page` is the order
     * detail route with sorting, filters, grouping and resizing.
     */
    variant?: 'page' | 'embedded'
    /** Page variant only: the detail page's Show Actions toggle. */
    showActions?: boolean
    /** Page variant only: groups rows by status or project. */
    groupBy?: 'status' | 'project' | null
  }>(),
  {
    canManage: false,
    canReceiveDeliveries: false,
    search: '',
    variant: 'embedded',
    showActions: true,
    groupBy: null,
  },
)

/**
 * Page variant only: shared by the detail page's Sort by menu and the
 * column headers. `undefined` means unsorted, as DataTable expects.
 */
const sortField = defineModel<string | undefined>('sortField')
const sortOrder = defineModel<number | undefined>('sortOrder')

const emit = defineEmits<{
  deliver: [orderId: number, item: OrderItemResponse]
  remove: [orderId: number, item: OrderItemResponse]
  move: [item: OrderItemResponse]
  viewHistory: [item: OrderItemResponse]
  updated: []
}>()

const { t } = useI18n()
const ordersStore = useOrdersStore()
const hostStore = useHostStore()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { formatPrice, formatPositionPrice, orderItemStatusSeverity } = useOrderFormatters()
const boughtItemDetail = useBoughtItemDetail()
const madeItemDetail = useMadeItemDetail()

const isPage = computed(() => props.variant === 'page')

const orderItems = computed(() => props.order.items ?? [])

const { editingItems, startEdit, cancelEdit, isEditing, editState, editErrors, saveItemEdit } =
  useOrderItemInlineEdit({
    items: orderItems,
    updateItem: (itemId, payload) => ordersStore.updateItem(props.order.id, itemId, payload),
    onSaved: () => emit('updated'),
    defaultErrorMessage: t('orders.items.errors.unknown'),
  })

const {
  filters,
  onFiltersUpdate,
  hasActiveFilters,
  clearFilters,
  statusOptions,
  groupedItems,
  groupRowsBy,
  rowClass,
} = useOrderItemRows(props, isEditing)

const {
  markingOrdered,
  markItemOrdered,
  permissions,
  cm,
  contextMenuItem,
  onRowContextMenu,
  contextMenuItems,
  overflowMenu,
  overflowItem,
  openOverflow,
  overflowMenuItems,
  isBusy,
  settleConfirm,
  settleConfirmVisible,
  confirmSettle,
} = useOrderItemRowMenus(props, {
  edit: startEdit,
  move: (item) => emit('move', item),
  deliver: (item) => emit('deliver', props.order.id, item),
  viewHistory: (item) => emit('viewHistory', item),
  remove: (item) => emit('remove', props.order.id, item),
  updated: () => emit('updated'),
})

// The actions cell holds an edited row's save and cancel buttons, so a
// hidden actions column still shows while any row is being edited.
const actionsColumnVisible = computed(
  () => props.showActions || Object.keys(editingItems.value).length > 0,
)

// Writes a range filter's value from its own update event and reapplies it.
function applyFilter(
  filterModel: { value: unknown },
  filterCallback: () => void,
  value: unknown,
): void {
  filterModel.value = value
  filterCallback()
}

defineExpose({ clearFilters, hasActiveFilters })
</script>

<template>
  <div :class="['items-panel', 'fixed-layout-table', { 'items-panel--page': isPage }]">
    <Message
      v-for="failed in editErrors"
      :key="failed.id"
      severity="error"
      :closable="false"
      size="small"
      class="edit-error"
    >
      {{ t('orders.items.columns.position') }} {{ failed.position }}: {{ failed.error }}
    </Message>

    <DataTable
      :value="groupedItems"
      data-key="id"
      class="phone-columns"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      :row-class="rowClass"
      :scrollable="isPage"
      :scroll-height="isPage ? 'flex' : undefined"
      :filter-display="isPage ? 'row' : undefined"
      :filters="isPage ? filters : undefined"
      @update:filters="onFiltersUpdate"
      :removable-sort="isPage"
      :resizable-columns="isPage"
      :column-resize-mode="isPage ? 'expand' : undefined"
      :row-group-mode="isPage && groupBy ? 'subheader' : undefined"
      :group-rows-by="isPage ? groupRowsBy : undefined"
      v-model:sort-field="sortField"
      v-model:sort-order="sortOrder"
      v-model:context-menu-selection="contextMenuItem"
      context-menu
      @row-contextmenu="onRowContextMenu"
    >
      <template v-if="isPage && groupBy" #groupheader="{ data }">
        <div class="group-header">
          <i v-if="groupBy === 'status'" class="mdi mdi-flag-outline" aria-hidden="true" />
          <i v-else class="mdi mdi-folder-outline" aria-hidden="true" />
          <span class="group-header-label">{{
            groupBy === 'status' ? data._statusGroup : data._projectGroup
          }}</span>
        </div>
      </template>

      <template #empty>
        <EmptyState :message="t('orders.items.empty')" />
      </template>

      <Column
        v-if="actionsColumnVisible"
        :frozen="isPage"
        style="width: 10rem"
        body-class="item-actions-cell"
      >
        <template #body="{ data }: { data: OrderItemResponse }">
          <OrderItemActionsCell
            :item="data"
            :permissions="permissions"
            :is-page="isPage"
            :editing="isEditing(data.id)"
            :saving="isEditing(data.id) && editState(data.id).saving"
            :marking-ordered="markingOrdered.isPending(data.id)"
            :busy="isBusy(data)"
            @save="saveItemEdit(data)"
            @cancel="cancelEdit(data.id)"
            @deliver="emit('deliver', order.id, data)"
            @mark-ordered="markItemOrdered(data.id)"
            @edit="startEdit(data)"
            @overflow="(event) => openOverflow(data, event)"
          />
        </template>
      </Column>

      <Column
        field="position"
        class="phone-row-number"
        :header="t('orders.items.columns.position')"
        :sortable="isPage"
        :frozen="isPage"
        style="width: 4rem"
      >
        <template #body="{ data }: { data: OrderItemResponse }">
          <InputNumber
            v-if="isEditing(data.id)"
            v-model="editState(data.id).position"
            :min="1"
            :input-style="{ width: '3.5rem' }"
            size="small"
          />
          <span v-else>{{ data.position }}</span>
        </template>
      </Column>

      <Column
        class="phone-col"
        field="status"
        :header="t('orders.items.columns.status')"
        :sortable="isPage"
        :show-filter-menu="false"
        style="width: 8rem"
      >
        <template #body="{ data }: { data: OrderItemResponse }">
          <Tag
            :value="t(`orders.items.status.${data.status}`)"
            :severity="orderItemStatusSeverity(data.status)"
          />
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <MultiSelect
            v-model="filterModel.value"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('orders.filters.any')"
            :aria-label="t('common.filterBy', { column: t('orders.items.columns.status') })"
            size="small"
            fluid
            @change="filterCallback()"
          />
        </template>
      </Column>

      <Column
        class="phone-col"
        field="quantity"
        :header="t('orders.items.columns.quantity')"
        :sortable="isPage"
        :show-filter-menu="false"
        :style="{ width: isPage ? '10rem' : '8rem' }"
      >
        <template #filter="{ filterModel, filterCallback }">
          <NumberRangeRowFilter
            :model-value="filterModel.value"
            :fraction-digits="3"
            :column="t('orders.items.columns.quantity')"
            @update:model-value="(value) => applyFilter(filterModel, filterCallback, value)"
          />
        </template>
        <template #body="{ data }: { data: OrderItemResponse }">
          <OrderItemQuantityEdit
            v-if="isEditing(data.id)"
            v-model:quantity="editState(data.id).quantity"
            v-model:unit="editState(data.id).unit"
            :quantity-locked="!orderItemActionGates.editQuantity(data)"
            :unit-locked="!orderItemActionGates.editUnit(data)"
          />
          <OrderItemQuantityCell v-else :item="data" />
        </template>
      </Column>

      <Column
        field="project_number"
        :header="t('orders.items.columns.project')"
        :sortable="isPage"
        :show-filter-menu="false"
        style="width: 14rem"
      >
        <template #body="{ data }: { data: OrderItemResponse }">
          <ProjectSelect
            v-if="isEditing(data.id)"
            v-model="editState(data.id).selectedProject"
            :aria-label="t('orders.items.columns.project')"
            size="small"
            style="min-width: 12rem"
          />
          <OrderItemProjectCell v-else :item="data" />
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <OrderItemTextFilter
            v-model="filterModel.value"
            :column="t('orders.items.columns.project')"
            @input="filterCallback()"
          />
        </template>
      </Column>

      <Column v-if="hostStore.storageEnabled" class="phone-thumbnail" style="width: 4rem" body-class="item-thumbnail">
        <template #body="{ data }: { data: OrderItemResponse }">
          <MadeItemThumbnailCell
            v-if="data.line_type === 'MADE' && data.made_item_id !== null"
            :item-id="data.made_item_id!"
            :item-name="data.item_article_name"
          />
          <BoughtItemThumbnailCell
            v-else-if="data.line_type !== 'MADE' && data.bought_item_id !== null"
            :item-id="data.bought_item_id!"
            :item-name="data.item_article_name"
          />
        </template>
      </Column>

      <Column
        class="phone-col"
        filter-field="_itemText"
        :header="t('orders.items.columns.item')"
        :show-filter-menu="false"
        body-class="item-name-cell"
        style="width: 18rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <OrderItemTextFilter
            v-model="filterModel.value"
            :column="t('orders.items.columns.item')"
            @input="filterCallback()"
          />
        </template>
        <template #body="{ data }: { data: OrderItemResponse }">
          <template v-if="isEditing(data.id)">
            <OrderItemCellMadeEdit v-if="data.line_type === 'MADE'" :item="data" />
            <OrderItemCellSourceEdit v-else-if="data.line_type === 'SOURCE'" :item="data" />
            <OrderItemCellVirtualEdit
              v-else-if="data.line_type === 'VIRTUAL'"
              :original-item-id="editState(data.id).originalItemId"
              v-model:virtual-name="editState(data.id).virtualName"
              :item-locked="!orderItemActionGates.editIdentity(data)"
              v-model:selected-item="editState(data.id).selectedItem"
              v-model:substitute-reason="editState(data.id).substituteReason"
            />
            <OrderItemCellBoughtEdit
              v-else
              :original-item-id="editState(data.id).originalItemId"
              :item-locked="!orderItemActionGates.editIdentity(data)"
              v-model:selected-item="editState(data.id).selectedItem"
              v-model:substitute-reason="editState(data.id).substituteReason"
            />
          </template>
          <OrderItemCellView
            v-else
            :item="data"
            @open-made-item="madeItemDetail.openDetailById"
            @open-bought-item="boughtItemDetail.openDetailById"
          />
        </template>
      </Column>

      <Column
        field="expected_delivery_date"
        :header="t('orders.items.columns.expectedDelivery')"
        :sortable="isPage"
        :show-filter-menu="false"
        style="width: 8rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <DemandDateRangeFilter
            :model-value="filterModel.value"
            :placeholder="t('orders.filters.filterBy')"
            @update:model-value="(value) => applyFilter(filterModel, filterCallback, value ?? null)"
            @clear-click="applyFilter(filterModel, filterCallback, null)"
          />
        </template>
        <template #body="{ data }: { data: OrderItemResponse }">
          <DatePicker
            v-if="isEditing(data.id)"
            v-model="editState(data.id).expected_delivery_date"
            show-button-bar
            show-clear
            size="small"
          />
          <span v-else class="nowrap">{{ data.expected_delivery_date ?? getEmptyPlaceholder() }}</span>
        </template>
      </Column>

      <Column
        field="expected_pickup_date"
        :header="t('orders.items.columns.expectedPickup')"
        :sortable="isPage"
        :show-filter-menu="false"
        style="width: 9rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <DemandDateRangeFilter
            :model-value="filterModel.value"
            :placeholder="t('orders.filters.filterBy')"
            @update:model-value="(value) => applyFilter(filterModel, filterCallback, value ?? null)"
            @clear-click="applyFilter(filterModel, filterCallback, null)"
          />
        </template>
        <template #body="{ data }: { data: OrderItemResponse }">
          <DatePicker
            v-if="isEditing(data.id)"
            v-model="editState(data.id).expected_pickup_date"
            show-button-bar
            show-clear
            size="small"
          />
          <OrderItemPickupCell v-else :item="data" />
        </template>
      </Column>

      <Column
        field="delivery_date"
        :header="t('orders.items.columns.deliveryDate')"
        :sortable="isPage"
        :show-filter-menu="false"
        style="width: 8rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <DemandDateRangeFilter
            :model-value="filterModel.value"
            :placeholder="t('orders.filters.filterBy')"
            @update:model-value="(value) => applyFilter(filterModel, filterCallback, value ?? null)"
            @clear-click="applyFilter(filterModel, filterCallback, null)"
          />
        </template>
        <template #body="{ data }: { data: OrderItemResponse }">
          <span class="nowrap" :title="formatDateTimeOrEmpty(data.delivery_date)">{{
            formatDateOrDash(data.delivery_date)
          }}</span>
        </template>
      </Column>

      <Column
        field="price"
        filter-field="_priceMajor"
        :header="t('orders.items.columns.price')"
        :sortable="isPage"
        :show-filter-menu="false"
        :style="{ width: isPage ? '10rem' : '7rem' }"
      >
        <template #filter="{ filterModel, filterCallback }">
          <NumberRangeRowFilter
            :model-value="filterModel.value"
            :fraction-digits="2"
            :column="t('orders.items.columns.price')"
            @update:model-value="(value) => applyFilter(filterModel, filterCallback, value)"
          />
        </template>
        <template #body="{ data }: { data: OrderItemResponse }">
          <InputNumber
            v-if="isEditing(data.id)"
            v-model="editState(data.id).price"
            :min="0"
            :min-fraction-digits="2"
            :max-fraction-digits="2"
            :prefix="currencyInputPrefix()"
            :input-style="{ width: '6rem' }"
            size="small"
          />
          <span v-else>{{ formatPrice(data.price) }}</span>
        </template>
      </Column>

      <Column :header="t('orders.items.columns.pricePosition')" style="width: 7rem">
        <template #body="{ data }: { data: OrderItemResponse }">{{ formatPositionPrice(data) }}</template>
      </Column>

      <Column
        field="note"
        :header="t('orders.items.columns.note')"
        :show-filter-menu="false"
        style="width: 14rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <OrderItemTextFilter
            v-model="filterModel.value"
            :column="t('orders.items.columns.note')"
            @input="filterCallback()"
          />
        </template>
        <template #body="{ data }: { data: OrderItemResponse }">
          <InputText
            v-if="isEditing(data.id)"
            v-model="editState(data.id).note"
            size="small"
            style="width: 14rem"
          />
          <span v-else class="note-cell">{{ data.note ?? getEmptyPlaceholder() }}</span>
        </template>
      </Column>

      <Column
        field="storage_place"
        :header="t('orders.items.columns.storagePlace')"
        :show-filter-menu="false"
        style="width: 8rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <OrderItemTextFilter
            v-model="filterModel.value"
            :column="t('orders.items.columns.storagePlace')"
            @input="filterCallback()"
          />
        </template>
        <template #body="{ data }: { data: OrderItemResponse }">
          <span class="nowrap">{{ data.storage_place ?? getEmptyPlaceholder() }}</span>
        </template>
      </Column>

      <!-- The quote request the line was awarded from, if any. -->
      <Column :header="t('orders.items.columns.quoteRequest')" style="width: 8rem">
        <template #body="{ data }: { data: OrderItemResponse }">
          <RouterLink
            v-if="data.quote_request_id !== null"
            class="quote-request-link nowrap"
            :to="`/procurement/quotes/${data.quote_request_id}`"
            @click.stop
            >{{ data.quote_request_number }}</RouterLink
          >
          <span v-else class="muted-cell">{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>

      <!-- The trailing empty column absorbs the width the real columns do
           not need, see the fixed table layout below. -->
      <Column />
    </DataTable>
  </div>

  <ContextMenu ref="cm" :model="contextMenuItems" :pt="menuPt" @hide="contextMenuItem = null" />
  <ConfirmActionDialog
    v-if="settleConfirm"
    v-model:visible="settleConfirmVisible"
    :header="settleConfirm.header"
    :message="settleConfirm.message"
    :confirm-label="settleConfirm.confirmLabel"
    confirm-severity="warn"
    @confirm="confirmSettle"
  />

  <Menu ref="overflowMenu" :model="overflowMenuItems" :pt="menuPt" popup @hide="overflowItem = null" />

  <BoughtItemDetailDialog
    v-model:visible="boughtItemDetail.showDetail.value"
    :item="boughtItemDetail.detailItem.value"
  />

  <MadeItemDetailDialog
    v-model:visible="madeItemDetail.showDetail.value"
    :item="madeItemDetail.detailItem.value"
  />
</template>

<style scoped lang="scss">
// Under a fixed layout (.fixed-layout-table) every real column keeps its
// explicit width, so the surplus goes to the trailing empty column alone
// instead of being spread across all of them, and the container scrolls
// horizontally itself since both variants' ancestors clip overflow.
.items-panel {
  padding: var(--space-1) var(--space-1) var(--space-4);
}

.items-panel--page {
  padding: 0;
  height: 100%;
  min-height: 0;
}

.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}

.edit-error {
  margin-bottom: var(--space-2);
}

// Row states. Striping, borders and hover come from the theme.
:deep(.row-delivered) > td {
  opacity: 0.6;
}

:deep(.row-search-match) > td {
  background: color-mix(in srgb, var(--p-yellow-500) 12%, transparent);
}

:deep(.item-actions-cell),
:deep(.item-thumbnail) {
  white-space: nowrap;
}

:deep(.item-name-cell) {
  white-space: normal;
}

.nowrap {
  white-space: nowrap;
}

.quote-request-link {
  color: inherit;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.muted-cell {
  color: var(--p-text-muted-color);
}

.note-cell {
  display: inline-block;
  max-width: 16rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--p-text-muted-color);
}
</style>
