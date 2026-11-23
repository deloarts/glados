import { computed, ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { useClipboard } from '@/core/composables/useClipboard'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useHostStore } from '@/core/host/stores/hostStore'
import { Permission } from '@/core/auth/permissions'
import { anyHasAction, hasAction, offersAction } from '@/core/utils/lifecycleActions'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { hasDeliverableLines, orderActionGates } from './useOrderItemActions'

import type { MenuItem } from 'openvue/menuitem'
import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { OrderResponse } from '../types/ordersResponse'
import type { OrderMailType } from './useOrderMailComposer'

export interface OrdersTableMenuActions {
  canWrite: Ref<boolean>
  canManage: Ref<boolean>
  canReceiveDeliveries: Ref<boolean>
  canSendMail: Ref<boolean>
  canPrint: Ref<boolean>
  editFieldMenuItems: (order: OrderResponse) => MenuItem[]
  fileMenuItems: (order: OrderResponse) => MenuItem[]
  openAddItem: (order: OrderResponse) => void
  markAllItemsRequested: (orderId: number) => Promise<void>
  markAllItemsOrdered: (orderId: number) => Promise<void>
  openDeliverAllDialog: (orderId: number) => void
  composeOrderMail: (order: OrderResponse, mailType: OrderMailType) => Promise<void>
  startCancelConfirm: (order: OrderResponse) => void
  downloadingDocketId: Ref<number | null>
  downloadOrderDocket: (order: OrderResponse) => Promise<void>
  printingDocketId: Ref<number | null>
  printOrderDocket: (order: OrderResponse) => Promise<void>
}

// The row-action "edit" popup menu and the row context menu, both OpenVue
// Menu-family components driven off whichever order they were last opened
// for.
export function useOrdersTableMenus(actions: OrdersTableMenuActions) {
  const { t } = useI18n()
  const { toastOnError } = useErrorToast()
  const router = useRouter()
  const { copyToClipboard } = useClipboard()
  const hostStore = useHostStore()
  const { missing, missingForAction } = useMissingPermission()

  // A mark-all entry names the permission it lacks: write:orders, else the
  // extra permission the backend blocks it by on the lines whose state
  // allows it, which is manage:orders on a submitted order.
  function markAllBlocked(order: OrderResponse, action: LifecycleAction): string | undefined {
    const lacking = missing(Permission.WRITE_ORDERS)
    if (lacking) return lacking
    const items = order.items ?? []
    if (anyHasAction(items, action)) return undefined
    const blocked = items.find((item) => offersAction(item, action))
    return (blocked && missingForAction(blocked, action)) || undefined
  }

  const editMenu = ref()
  const editMenuOrder = ref<OrderResponse | null>(null)

  function openEditMenu(order: OrderResponse, event: Event): void {
    editMenuOrder.value = order
    editMenu.value?.toggle(event)
  }

  const editMenuItems = computed<MenuItem[]>(() =>
    editMenuOrder.value ? actions.editFieldMenuItems(editMenuOrder.value) : [],
  )

  // The edit submenu stays open while any field is editable, since the
  // supplier order numbers keep write:orders after the header fields need
  // manage:orders; each entry carries its own state and reason.
  function editFieldsMenuEntry(order: OrderResponse): MenuItem {
    const items = actions.editFieldMenuItems(order)
    const noneEditable = items.every((item) => item.disabled === true)
    return {
      label: t('orders.actions.edit'),
      icon: 'mdi mdi-pencil',
      disabled: noneEditable,
      title:
        noneEditable && offersAction(order, 'edit')
          ? missingForAction(order, 'edit', Permission.WRITE_ORDERS) || undefined
          : undefined,
      items,
    }
  }

  const cm = ref()
  const contextMenuItem = ref<OrderResponse | null>(null)

  function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
    cm.value?.show(event.originalEvent)
  }

  function openOrder(order: OrderResponse): void {
    void router.push(`/procurement/orders/${order.id}`)
  }

  const contextMenuItems = computed<MenuItem[]>(() => {
    const order = contextMenuItem.value
    if (!order) return []

    const orderItems = order.items ?? []
    const hasPending = anyHasAction(orderItems, 'mark_requested')
    const hasPendingOrRequested = anyHasAction(orderItems, 'mark_ordered')
    const hasDeliverable = hasDeliverableLines(order)
    const isCancelable = hasAction(order, 'cancel')

    return [
      {
        label: t('orders.actions.open'),
        icon: 'mdi mdi-open-in-new',
        command: () => openOrder(order),
      },
      { separator: true },
      editFieldsMenuEntry(order),
      {
        label: t('orders.actions.addItem'),
        icon: 'mdi mdi-plus',
        disabled: !orderActionGates.addItem(order, actions.canWrite.value),
        title: offersAction(order, 'add_item')
          ? missingForAction(order, 'add_item', Permission.WRITE_ORDERS) || undefined
          : undefined,
        command: () => actions.openAddItem(order),
      },
      {
        label: t('orders.actions.addFile'),
        icon: 'mdi mdi-paperclip',
        disabled: !actions.canWrite.value || !hostStore.storageEnabled,
        title: missing(Permission.WRITE_ORDERS) || undefined,
        items: actions.fileMenuItems(order),
      },
      { separator: true },
      {
        label: t('orders.actions.markAllRequested'),
        icon: 'mdi mdi-message-question-outline',
        disabled: !actions.canWrite.value || !hasPending,
        title: markAllBlocked(order, 'mark_requested'),
        command: () =>
          void actions
            .markAllItemsRequested(order.id)
            .catch(toastOnError(t('orders.actions.markAllRequested'))),
      },
      {
        label: t('orders.actions.markAllOrdered'),
        icon: 'mdi mdi-cart-check',
        disabled: !actions.canWrite.value || !hasPendingOrRequested,
        title: markAllBlocked(order, 'mark_ordered'),
        command: () =>
          void actions.markAllItemsOrdered(order.id).catch(toastOnError(t('orders.actions.markAllOrdered'))),
      },
      { separator: true },
      {
        label: t('orders.actions.deliverAll'),
        icon: 'mdi mdi-package-variant-closed-check',
        disabled: !actions.canReceiveDeliveries.value || !hasDeliverable,
        title: missing(Permission.RECEIVE_DELIVERIES) || undefined,
        command: () => actions.openDeliverAllDialog(order.id),
      },
      { separator: true },
      {
        label: t('orders.actions.requestMail'),
        icon: 'mdi mdi-email-arrow-right-outline',
        disabled: !actions.canSendMail.value,
        title: missing(Permission.SEND_MAIL) || undefined,
        command: () => void actions.composeOrderMail(order, 'request'),
      },
      {
        label: t('orders.actions.orderMail'),
        icon: 'mdi mdi-email-fast-outline',
        disabled: !actions.canSendMail.value,
        title: missing(Permission.SEND_MAIL) || undefined,
        command: () => void actions.composeOrderMail(order, 'order'),
      },
      { separator: true },
      {
        label: t('orders.actions.cancel'),
        icon: 'mdi mdi-close-circle-outline',
        disabled: !actions.canWrite.value || !isCancelable,
        // Past REQUESTED a cancel also needs manage:orders.
        title: offersAction(order, 'cancel')
          ? missingForAction(order, 'cancel', Permission.WRITE_ORDERS) || undefined
          : undefined,
        command: () => actions.startCancelConfirm(order),
      },
      { separator: true },
      {
        label: t('orders.actions.downloadDocket'),
        icon: 'mdi mdi-file-document-outline',
        disabled: !actions.canPrint.value || actions.downloadingDocketId.value === order.id,
        title: missing(Permission.PRINT_DOCUMENTS) || undefined,
        command: () => void actions.downloadOrderDocket(order),
      },
      {
        label: t('orders.actions.printDocket'),
        icon: 'mdi mdi-printer-outline',
        disabled: !actions.canPrint.value || actions.printingDocketId.value === order.id,
        title: missing(Permission.PRINT_DOCUMENTS) || undefined,
        command: () => void actions.printOrderDocket(order),
      },
      { separator: true },
      {
        label: t('common.copyUuid'),
        icon: 'mdi mdi-content-copy',
        command: () => void copyToClipboard(order.public_id),
      },
    ]
  })

  return {
    editMenu,
    editMenuOrder,
    openEditMenu,
    editMenuItems,
    cm,
    contextMenuItem,
    onRowContextMenu,
    contextMenuItems,
  }
}
