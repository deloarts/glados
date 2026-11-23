<script setup lang="ts">
import { computed, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'
import { usePhoneLayout } from '@/core/composables/usePhoneLayout'

import { usePermissions } from '@/core/composables/usePermissions'
import { extractApiError } from '@/core/utils/errors'
import { useOrdersStore } from '../stores/ordersStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { Permission } from '@/core/auth/permissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useControlsBarFit } from '@/shared/composables/useControlsBarFit'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'

import { MailComposeDialog } from '@/features/mail'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'

import { useOrderDetail } from '../composables/useOrderDetail'
import { usePageTitle } from '@/core/composables/usePageTitle'
import { useOrderDetailToolbar, menuItemLabel, runMenuItem } from '../composables/useOrderDetailToolbar'
import { useOrderDetailViews } from '../composables/useOrderDetailViews'
import { useOrderMailComposer } from '../composables/useOrderMailComposer'
import { useOrderFileUpload } from '../composables/useOrderFileUpload'
import { useOrderEditFields } from '../composables/useOrderEditFields'
import { orderActionGates } from '../composables/useOrderItemActions'
import { hasAction, offersAction } from '@/core/utils/lifecycleActions'
import OrderItemsTable from '../components/OrderItemsTable.vue'
import OrderItemCreateForm from '../components/OrderItemCreateForm.vue'
import DeliverItemDialog from '../components/DeliverItemDialog.vue'
import DeliveryHistoryDialog from '../components/DeliveryHistoryDialog.vue'
import DeliverAllDialog from '../components/DeliverAllDialog.vue'
import MoveOrderItemDialog from '../components/MoveOrderItemDialog.vue'
import OrderFieldEditDialog from '../components/OrderFieldEditDialog.vue'
import OrderMailPostSendDialog from '../components/OrderMailPostSendDialog.vue'
import OrderExtraCostsDialog from '../components/OrderExtraCostsDialog.vue'
import OrderDetailInfoBar from '../components/OrderDetailInfoBar.vue'
import OrderPrintButton from '../components/OrderPrintButton.vue'
import OrderDetailSidePanel from '../components/OrderDetailSidePanel.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'

import type { MenuItem } from 'openvue/menuitem'
import type { OrderItemResponse, OrderResponse } from '../types/ordersResponse'
import { useDialogTarget } from '@/shared/composables/useDialogTarget'
import { HelpButton } from '@/shared/help'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { hasPermission } = usePermissions()
const hostStore = useHostStore()
const ordersStore = useOrdersStore()
const confirm = useConfirm()
const toast = useAppToast()
const { fileMenuItems } = useOrderFileUpload()
const { dialogRef: editFieldDialog, menuItems: editFieldMenuItems } = useOrderEditFields()
const {
  composeOrderMail,
  dialogVisible: mailDialogVisible,
  dialogState: mailDialogState,
  pendingOrder: mailPendingOrder,
  pendingMailType: mailPendingType,
  showPostSend: showPostSendDialog,
  onMailSent,
} = useOrderMailComposer()

// The route constrains :id to `\d+`, so this can never be NaN.
const orderId = Number(route.params.id)

const { order, loading, notFound, loadError, reload } = useOrderDetail(orderId)

watchLoadingBar(loading)

const pageHeading = computed(() =>
  order.value ? t('orders.detail.title', { number: order.value.order_number }) : t('pageTitles.orderDetail'),
)
const { setPageTitle } = usePageTitle()
watch(pageHeading, setPageTitle, { immediate: true })

const canWrite = computed(() => hasPermission(Permission.WRITE_ORDERS))
const canManage = computed(() => hasPermission(Permission.MANAGE_ORDERS))
const canReceiveDeliveries = computed(() => hasPermission(Permission.RECEIVE_DELIVERIES))
const canSendMail = computed(() => hasPermission(Permission.SEND_MAIL))
const { missing, missingForAction } = useMissingPermission()
const sendMailBlocked = computed(() => missing(Permission.SEND_MAIL))

// Extra costs follow the order's edit rule: write:orders while it is a
// draft or requested, manage:orders after that; a canceled order takes none.
const extraCostsDialog = ref<InstanceType<typeof OrderExtraCostsDialog> | null>(null)
const extraCostsBlocked = computed(() => {
  if (!order.value) return ''
  const submitted = !['draft', 'requested'].includes(order.value.status)
  return submitted
    ? missing(Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS)
    : missing(Permission.WRITE_ORDERS)
})
const extraCostsDisabled = computed(
  () => extraCostsBlocked.value !== '' || order.value?.canceled_at !== null,
)

// ── Toolbar density ───────────────────────────────────────────────────
// Short of room, the edit fields collapse into one menu button first, then
// the mark-all actions, then the mails.
const { collapsed } = useControlsBarFit(useTemplateRef('controlsBar'), ['edit', 'markAll', 'mail'])
// A phone shows the order's lines only; the note and files panel beside
// them is for the desktop.
const { phoneMode } = usePhoneLayout()

// ── Views bar state ─────────────────────────────────────────────────────

const itemsTableRef = ref<InstanceType<typeof OrderItemsTable> | null>(null)
// Hidden by default; the row context menu carries every action anyway.
const showActionsColumn = ref(false)
const showFilesPanel = ref(true)
// The side column (note card over files card) resizes as one, dragging its
// leading edge like the other end-docked panels in the app.
const {
  width: sidePanelWidth,
  isResizing: isResizingSidePanel,
  onResizeStart: onSidePanelResizeStart,
  onResizeKey: onSidePanelResizeKey,
  min: sidePanelMin,
  max: sidePanelMax,
} = useResizablePanelWidth({
  defaultWidth: 420,
  min: 280,
  max: () => window.innerWidth * 0.7,
  dockedTo: 'end',
  storageKey: 'glados.orders.detailSidePanelWidth',
})
const {
  groupBy,
  sortField,
  sortOrder,
  groupByItems,
  sortByItems,
  hasActiveViewFilters,
  clearSort,
  clearViews,
} = useOrderDetailViews(itemsTableRef)

// ── Order-level actions ───────────────────────────────────────────────

const showDeliverAllDialog = ref(false)

watch(showDeliverAllDialog, (open, wasOpen) => {
  if (!open && wasOpen) void reload({ quiet: true })
})

const {
  hasPending,
  hasPendingOrRequested,
  hasDeliverable,
  markAllRequestedBlocked,
  markAllOrderedBlocked,
  deliverAllBlocked,
  markingRequested,
  markingOrdered,
  markAllRequested,
  markAllOrdered,
  showAddItem,
  addItemVirtual,
  openAddItem,
  addItemMenuItems,
  onMailAction,
  markAllMenuItems,
  mailMenuItems,
} = useOrderDetailToolbar({
  order,
  canWrite,
  canReceiveDeliveries,
  canSendMail,
  reload,
  composeOrderMail,
  openDeliverAll: () => {
    showDeliverAllDialog.value = true
  },
})
// New lines follow the order's add_item action, which an order someone
// canceled no longer offers; the header fields gate each edit menu entry.
const canAddItem = computed(
  () => order.value !== null && orderActionGates.addItem(order.value, canWrite.value),
)
// Each names the permission it lacks while the order's state allows it.
const editHeaderBlocked = computed(() =>
  offersAction(order.value, 'edit')
    ? missingForAction(order.value, 'edit', Permission.WRITE_ORDERS)
    : '',
)
const addItemBlocked = computed(() =>
  offersAction(order.value, 'add_item')
    ? missingForAction(order.value, 'add_item', Permission.WRITE_ORDERS)
    : '',
)
const addFileBlocked = computed(() => missing(Permission.WRITE_ORDERS))
const markAllBlocked = computed(() => missing(Permission.WRITE_ORDERS))
const isCancelable = computed(() => hasAction(order.value, 'cancel'))
// A cancel the state allows names the permission it lacks: write:orders, or
// manage:orders once the order is past REQUESTED.
const cancelBlocked = computed(() =>
  offersAction(order.value, 'cancel')
    ? missingForAction(order.value, 'cancel', Permission.WRITE_ORDERS)
    : '',
)

// Offered after a successful cancel. order_canceled has no per-supplier
// template, so it always uses the admin default.
function confirmNotifySupplierOfCancellation(canceledOrder: OrderResponse): void {
  confirm.require({
    message: t('orders.mail.notifyCanceledConfirm'),
    header: t('orders.mail.notifyCanceledTitle'),
    icon: 'mdi mdi-email-outline',
    rejectProps: { label: t('orders.mail.notifyCanceledSkip'), severity: 'secondary' },
    acceptProps: { label: t('orders.mail.notifyCanceledSend') },
    accept: () => {
      void composeOrderMail(canceledOrder, 'order_canceled')
    },
  })
}

function confirmCancelOrder(): void {
  async function onAccept(): Promise<void> {
    // Cancellation changes nothing the mail reads, so the pre-cancel object is
    // fine.
    const canceledOrder = order.value
    if (!canceledOrder) return
    try {
      await ordersStore.cancel(orderId, canceledOrder.edit_version)
      await reload({ quiet: true })
      if (canSendMail.value) confirmNotifySupplierOfCancellation(canceledOrder)
    } catch (e) {
      toast.error(
        t('orders.actions.cancel'),
        extractApiError(e) ?? t('orders.detail.errors.unknown'),
      )
    }
  }

  confirm.require({
    message: t('orders.actions.cancelConfirm'),
    header: t('orders.actions.cancel'),
    icon: 'mdi mdi-close-circle-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('orders.actions.cancel'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

// ── Toolbar popup menus ───────────────────────────────────────────────

const editMenu = ref()
const fileMenu = ref()
const markAllMenu = ref()
const mailMenu = ref()

const editMenuItems = computed<MenuItem[]>(() =>
  order.value ? editFieldMenuItems(order.value) : [],
)
// The compact edit button opens the field menu while any field is editable:
// the supplier order numbers stay open to write:orders after the header
// fields need manage:orders.
const canEditAnyField = computed(() => editMenuItems.value.some((item) => item.disabled !== true))

const addFileMenuItems = computed<MenuItem[]>(() => (order.value ? fileMenuItems(order.value) : []))

// The compact menus say why an entry is disabled, as the desktop buttons do.
const markAllMenuPt = {
  itemLink: (options: { context: { item: MenuItem } }) => ({
    'data-testid': 'mark-all-menu-item',
    ...disabledItemTooltipPt.itemLink(options),
  }),
}

function toggleMenu(menu: { toggle(event: Event): void } | undefined, event: Event): void {
  menu?.toggle(event)
}

// ── Item dialogs ──────────────────────────────────────────────────────

const {
  target: deliverTarget,
  visible: showDeliverDialog,
  open: openDeliverTarget,
} = useDialogTarget<OrderItemResponse>()

// orderId is unused; the page knows its order from the route.
function openDeliverDialog(_orderId: number, item: OrderItemResponse): void {
  openDeliverTarget(item)
}

const {
  target: historyTarget,
  visible: showHistoryDialog,
  open: openHistoryTarget,
} = useDialogTarget<OrderItemResponse>()

function openHistoryDialog(item: OrderItemResponse): void {
  openHistoryTarget(item)
}

function confirmRemoveItem(_orderId: number, item: OrderItemResponse): void {
  async function onAccept(): Promise<void> {
    try {
      await ordersStore.removeItem(orderId, item.id, item.edit_version)
      await reload({ quiet: true })
    } catch (e) {
      toast.error(
        t('orders.actions.removeItem'),
        extractApiError(e) ?? t('orders.detail.errors.unknown'),
      )
    }
  }

  confirm.require({
    message: t('orders.actions.removeItemConfirm'),
    header: t('orders.actions.removeItemConfirmTitle'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('orders.actions.removeItem'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

const moveTarget = ref<OrderItemResponse | null>(null)
const showMoveItemDialog = ref(false)

function openMoveItemDialog(item: OrderItemResponse): void {
  moveTarget.value = item
  showMoveItemDialog.value = true
}

// The dialogs write into the list store, which this page does not use, so
// the page reloads on close.
watch([showDeliverDialog, showMoveItemDialog], (open, wasOpen) => {
  if (open.some((isOpen, i) => !isOpen && wasOpen[i])) void reload({ quiet: true })
})
</script>

<template>
  <PageLayout wrap-menu :class="{ 'is-resizing-ew': isResizingSidePanel }" data-class="detail-data-row">
    <template #info>
      <OrderDetailInfoBar :order="order" />
    </template>

    <template #controls>
      <ControlsBar ref="controlsBar">
        <template #start>
          <Button
            icon="mdi mdi-arrow-left"
            :label="t('orders.detail.back')"
            severity="contrast"
            text
            @click="router.push('/procurement/orders')"
          />

          <template v-if="order">
            <Divider layout="vertical" />

            <span v-tooltip.bottom="addItemBlocked || undefined">
              <SplitButton
                :label="t('orders.actions.addItem')"
                icon="mdi mdi-plus"
                severity="contrast"
                text
                :disabled="!canAddItem"
                :model="addItemMenuItems"
                @click="openAddItem(false)"
              >
                <template #item="{ item, props: itemProps }">
                  <a
                    v-bind="itemProps.action"
                    v-tooltip.bottom="item.disabled ? item.title : undefined"
                  >
                    <span v-if="item.icon" :class="item.icon" />
                    <span>{{ item.label }}</span>
                  </a>
                </template>
              </SplitButton>
            </span>

            <span v-tooltip.bottom="addFileBlocked || undefined">
              <Button
                icon="mdi mdi-paperclip"
                :label="t('orders.actions.addFile')"
                severity="contrast"
                text
                :disabled="!canWrite || !hostStore.storageEnabled"
                @click="toggleMenu(fileMenu, $event)"
              />
            </span>

            <span v-tooltip.bottom="extraCostsBlocked">
              <Button
                icon="mdi mdi-cash-plus"
                :label="t('common.extraCosts.edit')"
                severity="contrast"
                text
                :disabled="extraCostsDisabled"
                data-testid="order-extra-costs"
                @click="extraCostsDialog?.open(order)"
              />
            </span>

            <span
              v-if="collapsed.edit"
              v-tooltip.bottom="(!canEditAnyField && editHeaderBlocked) || undefined"
            >
              <Button
                icon="mdi mdi-pencil"
                :label="t('orders.actions.edit')"
                severity="contrast"
                text
                :disabled="!canEditAnyField"
                @click="toggleMenu(editMenu, $event)"
              />
            </span>
            <template v-else>
              <Divider layout="vertical" />

              <span
                v-for="item in editMenuItems"
                :key="menuItemLabel(item)"
                v-tooltip.bottom="(item.disabled === true && item.title) || undefined"
              >
                <Button
                  :icon="item.icon"
                  :label="menuItemLabel(item)"
                  severity="contrast"
                  text
                  :disabled="item.disabled === true"
                  @click="runMenuItem(item, $event)"
                />
              </span>
            </template>

            <Divider layout="vertical" />

            <span v-if="collapsed.markAll" v-tooltip.bottom="markAllBlocked || undefined">
              <Button
                icon="mdi mdi-check-all"
                :label="t('orders.actions.markAll')"
                severity="contrast"
                text
                :disabled="!canWrite"
                :loading="markingRequested || markingOrdered"
                @click="toggleMenu(markAllMenu, $event)"
              />
            </span>
            <template v-else>
              <span v-tooltip.bottom="markAllRequestedBlocked || undefined">
                <Button
                  icon="mdi mdi-message-question-outline"
                  :label="t('orders.actions.markAllRequested')"
                  severity="contrast"
                  text
                  :disabled="!canWrite || !hasPending"
                  :loading="markingRequested"
                  @click="markAllRequested"
                />
              </span>
              <span v-tooltip.bottom="markAllOrderedBlocked || undefined">
                <Button
                  icon="mdi mdi-cart-check"
                  :label="t('orders.actions.markAllOrdered')"
                  severity="contrast"
                  text
                  :disabled="!canWrite || !hasPendingOrRequested"
                  :loading="markingOrdered"
                  @click="markAllOrdered"
                />
              </span>
              <span v-tooltip.bottom="deliverAllBlocked || undefined">
                <Button
                  icon="mdi mdi-package-variant-closed-check"
                  :label="t('orders.actions.deliverAll')"
                  severity="contrast"
                  text
                  :disabled="!canReceiveDeliveries || !hasDeliverable"
                  @click="showDeliverAllDialog = true"
                />
              </span>
            </template>

            <Divider layout="vertical" />

            <Button
              v-if="collapsed.mail"
              icon="mdi mdi-email-outline"
              :label="t('orders.actions.mail')"
              severity="contrast"
              text
              @click="toggleMenu(mailMenu, $event)"
            />
            <template v-else>
              <span v-tooltip.bottom="sendMailBlocked">
                <Button
                  icon="mdi mdi-email-arrow-right-outline"
                  :label="t('orders.actions.requestMail')"
                  severity="contrast"
                  text
                  :disabled="!canSendMail"
                  @click="onMailAction(order, 'request')"
                />
              </span>
              <span v-tooltip.bottom="sendMailBlocked">
                <Button
                  icon="mdi mdi-email-fast-outline"
                  :label="t('orders.actions.orderMail')"
                  severity="contrast"
                  text
                  :disabled="!canSendMail"
                  @click="onMailAction(order, 'order')"
                />
              </span>
            </template>

            <Divider layout="vertical" />

            <OrderPrintButton :order="order" />
            <span v-tooltip.bottom="cancelBlocked || undefined">
              <Button
                icon="mdi mdi-close-circle-outline"
                :label="t('orders.actions.cancel')"
                severity="contrast"
                text
                :disabled="!canWrite || !isCancelable"
                @click="confirmCancelOrder"
              />
            </span>
          </template>
        </template>
        <template #handbook>
          <ShareButton :public-id="order?.public_id" />
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>

    <template #views>
      <ViewsBar
        id-prefix="order-detail"
        :syncing="loading"
        :show-actions="showActionsColumn"
        :group-by-items="groupByItems"
        :group-by-active="!!groupBy"
        :sort-by-items="sortByItems"
        :sort-by-active="!!sortField"
        :has-active-filters="hasActiveViewFilters"
        @sync="reload()"
        @toggle-show-actions="showActionsColumn = !showActionsColumn"
        @clear-group-by="groupBy = null"
        @clear-sort-by="clearSort()"
        @clear="clearViews()"
      >
        <template v-if="hostStore.storageEnabled" #extra>
          <Divider layout="vertical" />
          <Button
            :label="t('orders.views.hideFilesPanel')"
            icon="mdi mdi-page-layout-sidebar-right"
            severity="contrast"
            :text="showFilesPanel"
            @click="showFilesPanel = !showFilesPanel"
          />
        </template>
      </ViewsBar>
    </template>

    <template v-if="!loading && !notFound && !loadError && order && !phoneMode" #panels-end>
      <PanelResizeHandle :width="sidePanelWidth" :min="sidePanelMin" :max="sidePanelMax" @start="onSidePanelResizeStart" @key="onSidePanelResizeKey" />
      <OrderDetailSidePanel
        :order="order"
        :can-write="canWrite"
        :show-files="hostStore.storageEnabled && showFilesPanel"
        :style="{ width: sidePanelWidth + 'px' }"
      />
    </template>

    <div v-if="loading" class="state-center" />
    <div v-else-if="notFound" class="state-center state-message">
      <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
      <span>{{ t('orders.detail.notFound') }}</span>
    </div>
    <div v-else-if="loadError" class="state-center state-message">
      <i class="mdi mdi-alert-outline state-icon" aria-hidden="true" />
      <span>{{ t('orders.detail.loadError') }}</span>
    </div>

    <OrderItemsTable
      v-else-if="order"
      ref="itemsTableRef"
      :order="order"
      :can-write="canWrite"
      :can-manage="canManage"
      :can-receive-deliveries="canReceiveDeliveries"
      variant="page"
      :show-actions="showActionsColumn"
      :group-by="groupBy"
      v-model:sort-field="sortField"
      v-model:sort-order="sortOrder"
      @deliver="openDeliverDialog"
      @remove="confirmRemoveItem"
      @move="openMoveItemDialog"
      @view-history="openHistoryDialog"
      @updated="reload({ quiet: true })"
    />
  </PageLayout>


  <Menu ref="editMenu" :model="editMenuItems" popup :pt="disabledItemTooltipPt" />
  <Menu ref="fileMenu" :model="addFileMenuItems" popup />
  <Menu ref="markAllMenu" :model="markAllMenuItems" popup :pt="markAllMenuPt" />
  <Menu ref="mailMenu" :model="mailMenuItems" popup :pt="disabledItemTooltipPt" />

  <DeliverItemDialog v-model:visible="showDeliverDialog" :order-id="orderId" :item="deliverTarget" />

  <DeliveryHistoryDialog v-model:visible="showHistoryDialog" :item="historyTarget" />

  <MoveOrderItemDialog v-model:visible="showMoveItemDialog" :item="moveTarget" />

  <OrderItemCreateForm
    v-if="order"
    v-model:visible="showAddItem"
    :order-id="order.id"
    :supplier-id="order.supplier_id"
    :initial-virtual="addItemVirtual"
    @created="reload({ quiet: true })"
  />

  <DeliverAllDialog v-model:visible="showDeliverAllDialog" :order-id="orderId" />

  <OrderFieldEditDialog ref="editFieldDialog" @saved="reload({ quiet: true })" />

  <OrderExtraCostsDialog ref="extraCostsDialog" @saved="reload({ quiet: true })" />

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
    @marked="reload({ quiet: true })"
  />
</template>

<style scoped lang="scss">
// The items table beside the side column.
:deep(.detail-data-row) {
  display: flex;
  flex-direction: row;
  // The drag handle provides the visible spacing.
  gap: var(--space-1);
}

.is-resizing-ew {
  user-select: none;
  cursor: ew-resize;
}

// ── State screens ─────────────────────────────────────────────────────

.state-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: var(--space-3);
}

.state-message {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-md);

  .state-icon {
    font-size: var(--font-size-3xl);
  }
}
</style>
