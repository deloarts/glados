<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { SupplierSearchFilter } from '@/features/suppliers'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import { MailComposeDialog } from '@/features/mail'

import { useOrdersStore } from '../stores/ordersStore'
import { useOrdersFiltersStore } from '../stores/ordersFiltersStore'
import { useOrderFormatters } from '../composables/useOrderFormatters'
import { useOrderMailComposer } from '../composables/useOrderMailComposer'
import { useOrderFileUpload } from '../composables/useOrderFileUpload'
import { useOrderEditFields } from '../composables/useOrderEditFields'
import { useOrderDocketDownload } from '../composables/useOrderDocketDownload'
import { useOrdersTableDialogs } from '../composables/useOrdersTableDialogs'
import { useOrdersTableRowExpansion } from '../composables/useOrdersTableRowExpansion'
import { useOrdersTableFilters } from '../composables/useOrdersTableFilters'
import { useOrdersTableRowMutations } from '../composables/useOrdersTableRowMutations'
import { useOrdersTableConfirmActions } from '../composables/useOrdersTableConfirmActions'
import { useOrdersTableMenus } from '../composables/useOrdersTableMenus'

import OrderItemCreateForm from './OrderItemCreateForm.vue'
import OrderItemsTable from './OrderItemsTable.vue'
import DeliverItemDialog from './DeliverItemDialog.vue'
import DeliveryHistoryDialog from './DeliveryHistoryDialog.vue'
import DeliverAllDialog from './DeliverAllDialog.vue'
import MoveOrderItemDialog from './MoveOrderItemDialog.vue'
import OrderFieldEditDialog from './OrderFieldEditDialog.vue'
import OrderMailPostSendDialog from './OrderMailPostSendDialog.vue'
import OrderFilesCell from './OrderFilesCell.vue'
import OrderFilesSection from './OrderFilesSection.vue'
import OrderRowActionsCell from './orders-table/OrderRowActionsCell.vue'
import OrderDateCell from './orders-table/OrderDateCell.vue'
import OrderExpectedDeliveryCell from './orders-table/OrderExpectedDeliveryCell.vue'
import { AgentBadge } from '@/features/agents'
import OrderDateRangeFilter from './orders-table/OrderDateRangeFilter.vue'
import { ORDERS_TABLE_FILTERS } from './orders-table/ordersTableColumns'

import type { OrderResponse } from '../types/ordersResponse'

const { t } = useI18n()

const ordersStore = useOrdersStore()
const filtersStore = useOrdersFiltersStore()
const hostStore = useHostStore()

watchLoadingBar(() => ordersStore.loading)
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { orderTotalPrice, orderStatusSeverity } = useOrderFormatters()
const {
  composeOrderMail,
  dialogVisible: mailDialogVisible,
  dialogState: mailDialogState,
  pendingOrder: mailPendingOrder,
  pendingMailType: mailPendingType,
  showPostSend: showPostSendDialog,
  onMailSent,
} = useOrderMailComposer()
const { fileMenuItems } = useOrderFileUpload()
const {
  dialogRef: editFieldDialog,
  open: openEditField,
  menuItems: editFieldMenuItems,
} = useOrderEditFields()

const canWrite = computed(() => hasPermission(Permission.WRITE_ORDERS))
const canManage = computed(() => hasPermission(Permission.MANAGE_ORDERS))
const canReceiveDeliveries = computed(() => hasPermission(Permission.RECEIVE_DELIVERIES))
const canSendMail = computed(() => hasPermission(Permission.SEND_MAIL))
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))

const { downloadingDocketId, downloadOrderDocket, printingDocketId, printOrderDocket } =
  useOrderDocketDownload()

const {
  addItemOrderId,
  addItemSupplierId,
  showAddItem,
  openAddItem,
  deliverTarget,
  showDeliverDialog,
  openDeliverDialog,
  historyTarget,
  showHistoryDialog,
  openHistoryDialog,
  deliverAllOrderId,
  showDeliverAllDialog,
  openDeliverAllDialog,
  moveTarget,
  showMoveItemDialog,
  openMoveItemDialog,
} = useOrdersTableDialogs()

const { expandedRows, onRowClick, onRowSelect } = useOrdersTableRowExpansion()

const {
  search,
  orderNumberFilter,
  noteFilter,
  storagePlaceFilter,
  statusFilter,
  supplierFilter,
  creatorFilter,
  groupBy,
  statusOptions,
  groupedItems,
  groupRowsBy,
  first,
  rows,
  fetchItems,
  onPage,
  orderedDateRange,
  expectedDeliveryDateRange,
  deliveredDateRange,
  createdDateRange,
  setOrderedDateRange,
  setExpectedDeliveryRange,
  setDeliveredDateRange,
  setCreatedDateRange,
  isExpectedDeliverySettable,
} = useOrdersTableFilters(expandedRows)

const { markingAllOrdered, markingAllRequested, markAllItemsOrdered, markAllItemsRequested } =
  useOrdersTableRowMutations()

const { openRemoveItemDialog, startCancelConfirm } = useOrdersTableConfirmActions(
  canSendMail,
  composeOrderMail,
)

const {
  editMenu,
  editMenuOrder,
  openEditMenu,
  editMenuItems,
  cm,
  contextMenuItem,
  onRowContextMenu,
  contextMenuItems,
} = useOrdersTableMenus({
  canWrite,
  canManage,
  canReceiveDeliveries,
  canSendMail,
  canPrint,
  editFieldMenuItems,
  fileMenuItems,
  openAddItem,
  markAllItemsRequested,
  markAllItemsOrdered,
  openDeliverAllDialog,
  composeOrderMail,
  startCancelConfirm,
  downloadingDocketId,
  downloadOrderDocket,
  printingDocketId,
  printOrderDocket,
})
</script>

<template>
  <DataTable
    :value="groupedItems"
    data-key="id"
    lazy
    paginator
    :total-records="ordersStore.total"
    :first="first"
    :rows="rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    @page="onPage"
    filter-display="row"
    :filters="ORDERS_TABLE_FILTERS"
    scrollable
    scroll-height="flex"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    resizable-columns
    column-resize-mode="expand"
    size="small"
    table-style="min-width: 60rem"
    :row-group-mode="groupBy ? 'subheader' : undefined"
    :group-rows-by="groupRowsBy"
    v-model:expanded-rows="expandedRows"
    v-model:context-menu-selection="contextMenuItem"
    selection-mode="single"
    @row-click="onRowClick"
    @row-select="onRowSelect"
    @row-contextmenu="onRowContextMenu"
    class="phone-columns clickable-rows"
  >
    <template v-if="groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i v-if="groupBy === 'status'" class="mdi mdi-flag-outline" aria-hidden="true" />
        <i v-else class="mdi mdi-truck-outline" aria-hidden="true" />
        <span class="group-header-label">{{
          groupBy === 'status' ? data._statusGroup : data._supplierGroup
        }}</span>
      </div>
    </template>

    <template #empty>
      <EmptyState />
    </template>

    <Column expander style="width: 3rem" frozen />

    <Column v-if="filtersStore.showActions" style="width: 10rem" frozen align-frozen="right">
      <template #body="{ data }: { data: OrderResponse }">
        <OrderRowActionsCell
          :order="data"
          :can-write="canWrite"
          :can-manage="canManage"
          :can-receive-deliveries="canReceiveDeliveries"
          :marking-all-requested-pending="markingAllRequested.isPending(data.id)"
          :marking-all-ordered-pending="markingAllOrdered.isPending(data.id)"
          @cancel="startCancelConfirm"
          @mark-all-requested="(order) => markAllItemsRequested(order.id)"
          @mark-all-ordered="(order) => markAllItemsOrdered(order.id)"
          @deliver-all="(order) => openDeliverAllDialog(order.id)"
          @edit="(order, event) => openEditMenu(order, event)"
          @add-item="openAddItem"
        />
      </template>
    </Column>

    <Column
      frozen
      header="#"
      class="phone-row-number"
      header-style="width: 3rem"
      body-class="row-number"
    >
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>

    <Column
      class="phone-col"
      field="order_number"
      :header="t('orders.columns.orderNumber')"
      style="width: 8rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: OrderResponse }">
        <div class="stack-cell">
          <span>
            <!-- .stop so opening the order doesn't also toggle the row's
                 expansion on the way up to the row-click handler. -->
            <RouterLink class="order-number-link" :to="`/procurement/orders/${data.id}`" @click.stop>
              <strong>{{ data.order_number }}</strong>
            </RouterLink>
            <AgentBadge kind="order" :public-id="data.public_id" />
          </span>
          <span
            v-if="data.supplier_order_numbers.length > 0"
            class="sub"
            data-testid="supplier-order-numbers"
            v-tooltip.bottom="t('orders.columns.supplierOrderNumbers')"
          >
            {{ data.supplier_order_numbers.join(', ') }}
          </span>
        </div>
      </template>
      <template #filter>
        <!-- Matches the supplier's numbers for the order too. -->
        <InputText
          v-model="orderNumberFilter"
          :placeholder="t('orders.filters.filterByOrderNumber')"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      class="phone-col"
      field="status"
      :header="t('orders.columns.status')"
      style="width: 14rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: OrderResponse }">
        <Tag
          :value="t(`orders.status.${data.status}`)"
          :severity="orderStatusSeverity(data.status)"
        />
      </template>
      <template #filter>
        <MultiSelect
          v-model="statusFilter"
          :aria-label="t('orders.columns.status')"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('orders.filters.any')"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      class="phone-col"
      field="supplier_name"
      :header="t('orders.columns.supplier')"
      style="width: 12rem"
      :show-filter-menu="false"
    >
      <template #filter>
        <SupplierSearchFilter v-model="supplierFilter" :placeholder="t('orders.filters.any')" />
      </template>
    </Column>

    <Column :header="t('orders.columns.total')" style="width: 6rem">
      <template #body="{ data }: { data: OrderResponse }">
        {{ data.items?.length ?? 0 }}
      </template>
    </Column>

    <Column :header="t('orders.columns.totalPrice')" style="width: 9rem" body-class="num-cell">
      <template #body="{ data }: { data: OrderResponse }">
        {{ orderTotalPrice(data) }}
      </template>
    </Column>

    <Column
      field="ordered_date"
      :header="t('orders.columns.orderedDate')"
      style="width: 14rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: OrderResponse }">
        <OrderDateCell :date="data.ordered_date" show-week-tag />
      </template>
      <template #filter>
        <OrderDateRangeFilter
          :model-value="orderedDateRange"
          @update:model-value="setOrderedDateRange"
          @clear="setOrderedDateRange(null)"
        />
      </template>
    </Column>

    <Column
      field="expected_delivery_date"
      :header="t('orders.columns.expectedDelivery')"
      style="width: 14rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: OrderResponse }">
        <OrderExpectedDeliveryCell
          :order="data"
          :can-write="canWrite"
          :is-settable="isExpectedDeliverySettable(data)"
          @set-expected-delivery="(order) => openEditField(order, 'expected_delivery_date')"
        />
      </template>
      <template #filter>
        <OrderDateRangeFilter
          :model-value="expectedDeliveryDateRange"
          @update:model-value="setExpectedDeliveryRange"
          @clear="setExpectedDeliveryRange(null)"
        />
      </template>
    </Column>

    <Column
      field="delivery_date"
      :header="t('orders.columns.deliveryDate')"
      style="width: 14rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: OrderResponse }">
        <OrderDateCell :date="data.delivery_date" show-week-tag />
      </template>
      <template #filter>
        <OrderDateRangeFilter
          :model-value="deliveredDateRange"
          @update:model-value="setDeliveredDateRange"
          @clear="setDeliveredDateRange(null)"
        />
      </template>
    </Column>

    <Column
      v-if="hostStore.storageEnabled"
      :header="t('orders.columns.files')"
      style="width: 14rem; min-width: 14rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: OrderResponse }">
        <OrderFilesCell :order="data" :can-write="canWrite" />
      </template>
    </Column>

    <Column :header="t('orders.columns.quoteRequests')" style="width: 9rem">
      <template #body="{ data }: { data: OrderResponse }">
        <span v-if="data.quote_requests.length > 0" class="quote-request-links">
          <RouterLink
            v-for="request in data.quote_requests"
            :key="request.id"
            class="order-number-link"
            :to="`/procurement/quotes/${request.id}`"
            @click.stop
            >{{ request.request_number }}</RouterLink
          >
        </span>
        <span v-else class="muted-cell">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>

    <Column field="note" :header="t('orders.columns.note')" :show-filter-menu="false">
      <template #filter>
        <InputText
          v-model="noteFilter"
          :placeholder="t('orders.filters.searchBy')"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="storage_place"
      :header="t('orders.columns.storagePlace')"
      :show-filter-menu="false"
    >
      <template #filter>
        <InputText
          v-model="storagePlaceFilter"
          :placeholder="t('orders.filters.searchBy')"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="created"
      :header="t('orders.columns.created')"
      style="width: 14rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: OrderResponse }">
        <UserDateCell :date="data.created" :user="data.creator" />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="creatorFilter"
          :range="createdDateRange"
          :column="t('orders.columns.created')"
          :placeholder="t('orders.filters.any')"
          @update:range="setCreatedDateRange"
        />
      </template>
    </Column>

    <Column />

    <!-- Expanded row: order items sub-table + files -->
    <template #expansion="{ data }: { data: OrderResponse }">
      <OrderItemsTable
        :order="data"
        :can-write="canWrite"
        :can-manage="canManage"
        :can-receive-deliveries="canReceiveDeliveries"
        :search="search"
        @deliver="openDeliverDialog"
        @remove="openRemoveItemDialog"
        @move="openMoveItemDialog"
        @view-history="openHistoryDialog"
      />
      <OrderFilesSection
        v-if="hostStore.storageEnabled && filtersStore.showOrderFiles"
        :order="data"
        :can-write="canWrite"
      />
    </template>
  </DataTable>

  <ContextMenu
    ref="cm"
    :model="contextMenuItems"
    :pt="disabledItemTooltipPt"
    @hide="contextMenuItem = null"
  />
  <Menu
    ref="editMenu"
    :model="editMenuItems"
    popup
    :pt="disabledItemTooltipPt"
    @hide="editMenuOrder = null"
  />
  <OrderFieldEditDialog ref="editFieldDialog" />

  <OrderItemCreateForm
    v-if="addItemOrderId !== null"
    v-model:visible="showAddItem"
    :order-id="addItemOrderId"
    :supplier-id="addItemSupplierId"
    @created="fetchItems"
  />

  <DeliverItemDialog
    v-model:visible="showDeliverDialog"
    :order-id="deliverTarget?.orderId ?? 0"
    :item="deliverTarget?.item ?? null"
  />

  <DeliveryHistoryDialog v-model:visible="showHistoryDialog" :item="historyTarget" />

  <DeliverAllDialog v-model:visible="showDeliverAllDialog" :order-id="deliverAllOrderId" />

  <MoveOrderItemDialog v-model:visible="showMoveItemDialog" :item="moveTarget" />

  <MailComposeDialog
    v-model:visible="mailDialogVisible"
    :to="mailDialogState.to"
    :cc="mailDialogState.cc"
    :reply-to="mailDialogState.replyTo"
    :subject="mailDialogState.subject"
    :body="mailDialogState.body"
    :warning="mailDialogState.warning"
    @sent="onMailSent"
  />

  <OrderMailPostSendDialog
    v-model:visible="showPostSendDialog"
    :order="mailPendingOrder"
    :mail-type="mailPendingType"
  />
</template>

<style scoped lang="scss">
.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}

.quote-request-links {
  display: flex;
  flex-direction: column;
}

.muted-cell {
  color: var(--p-text-muted-color);
}

.stack-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.sub {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.order-number-link {
  color: inherit;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}
</style>
