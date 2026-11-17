import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { MenuItem } from 'openvue/menuitem'
import type { DataTableRowContextMenuEvent } from 'openvue/datatable'

import { useAppToast } from '@/core/composables/useAppToast'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { extractApiError } from '@/core/utils/errors'
import { useRowMutationState } from '@/shared/composables/useRowMutationState'
import { useOrdersStore } from '../stores/ordersStore'
import { useOrderItemActions } from './useOrderItemActions'

import type { OrderItemResponse, OrderResponse } from '../types/ordersResponse'

export interface OrderItemRowMenusProps {
  order: OrderResponse
  canWrite: boolean
  canManage: boolean
  canReceiveDeliveries: boolean
}

export interface OrderItemRowMenusHandlers {
  edit: (item: OrderItemResponse) => void
  move: (item: OrderItemResponse) => void
  deliver: (item: OrderItemResponse) => void
  viewHistory: (item: OrderItemResponse) => void
  remove: (item: OrderItemResponse) => void
  updated: () => void
}

/**
 * Row actions of the order items table. One menu model serves the row's
 * context menu and the overflow button in its actions cell; the status
 * changes run here with a per-row pending state. Canceling a line, closing
 * it short or reopening it asks first, through the confirm dialog the table
 * renders from `settleConfirm`.
 */
export function useOrderItemRowMenus(
  props: OrderItemRowMenusProps,
  handlers: OrderItemRowMenusHandlers,
) {
  const ordersStore = useOrdersStore()
  const { t } = useI18n()
  const { toastOnError } = useErrorToast()
  const toast = useAppToast()

  const markingOrdered = useRowMutationState<number>()
  const markingRequested = useRowMutationState<number>()
  const markingReadyForPickup = useRowMutationState<number>()
  const settlingLine = useRowMutationState<number>()

  type SettleKind = 'cancel' | 'closeShort' | 'reopen'
  const settleTarget = ref<{ kind: SettleKind; item: OrderItemResponse } | null>(null)
  const settleConfirmVisible = ref(false)

  function askSettle(kind: SettleKind, item: OrderItemResponse): void {
    settleTarget.value = { kind, item }
    settleConfirmVisible.value = true
  }

  /**
   * What the table's confirm dialog shows for the pending cancel, close
   * short or reopen, null when none is pending.
   */
  const settleConfirm = computed(() => {
    const target = settleTarget.value
    if (!target) return null
    if (target.kind === 'cancel') {
      return {
        header: t('orders.actions.cancelItem'),
        message: t('orders.actions.cancelItemConfirm'),
        confirmLabel: t('orders.actions.cancelItem'),
      }
    }
    const item = target.item
    if (target.kind === 'reopen') {
      return {
        header: t('orders.actions.reopenItem'),
        message: t('orders.actions.reopenItemConfirm', {
          quantity: item.closed_short_from ?? item.quantity,
        }),
        confirmLabel: t('orders.actions.reopenItem'),
      }
    }
    return {
      header: t('orders.actions.closeShort'),
      message: t('orders.actions.closeShortConfirm', {
        delivered: item.quantity_delivered + (item.quantity_rejected_lost ?? 0),
        quantity: item.quantity,
      }),
      confirmLabel: t('orders.actions.closeShort'),
    }
  })

  async function confirmSettle(): Promise<void> {
    const target = settleTarget.value
    if (!target) return
    settleTarget.value = null
    const { item } = target
    if (target.kind === 'cancel') {
      await settle(item, t('orders.actions.cancelItem'), t('orders.actions.cancelItemSuccess'), () =>
        ordersStore.cancelItem(props.order.id, item.id, item.edit_version),
      )
      return
    }
    if (target.kind === 'reopen') {
      await settle(item, t('orders.actions.reopenItem'), t('orders.actions.reopenItemSuccess'), () =>
        ordersStore.reopenItem(props.order.id, item.id, item.edit_version),
      )
      return
    }
    await settle(item, t('orders.actions.closeShort'), t('orders.actions.closeShortSuccess'), () =>
      ordersStore.closeItemShort(props.order.id, item.id, item.edit_version),
    )
  }

  async function settle(
    item: OrderItemResponse,
    title: string,
    success: string,
    action: () => Promise<void>,
  ): Promise<void> {
    await settlingLine.run(item.id, async () => {
      try {
        await action()
        toast.success(title, success)
        handlers.updated()
      } catch (e) {
        toast.error(title, extractApiError(e) ?? t('orders.detail.errors.unknown'))
      }
    })
  }

  async function markItemOrdered(itemId: number): Promise<void> {
    await markingOrdered.run(itemId, async () => {
      await ordersStore.markItemOrdered(props.order.id, itemId)
      handlers.updated()
    })
  }

  async function markItemRequested(itemId: number): Promise<void> {
    await markingRequested.run(itemId, async () => {
      await ordersStore.markItemRequested(props.order.id, itemId)
      handlers.updated()
    })
  }

  async function markItemReadyForPickup(itemId: number): Promise<void> {
    await markingReadyForPickup.run(itemId, async () => {
      await ordersStore.markItemReadyForPickup(props.order.id, itemId)
      handlers.updated()
    })
  }

  const { itemMenuItems } = useOrderItemActions({
    edit: handlers.edit,
    move: handlers.move,
    markRequested: (item) =>
      void markItemRequested(item.id).catch(toastOnError(t('orders.actions.markRequested'))),
    markOrdered: (item) => void markItemOrdered(item.id).catch(toastOnError(t('orders.actions.markOrdered'))),
    markReadyForPickup: (item) =>
      void markItemReadyForPickup(item.id).catch(toastOnError(t('orders.actions.markReadyForPickup'))),
    deliver: handlers.deliver,
    viewHistory: handlers.viewHistory,
    cancelLine: (item) => askSettle('cancel', item),
    closeShort: (item) => askSettle('closeShort', item),
    reopen: (item) => askSettle('reopen', item),
    remove: handlers.remove,
  })

  const permissions = computed(() => ({
    canWrite: props.canWrite,
    canManage: props.canManage,
    canReceiveDeliveries: props.canReceiveDeliveries,
  }))

  const cm = ref()
  const contextMenuItem = ref<OrderItemResponse | null>(null)

  function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
    cm.value?.show(event.originalEvent)
  }

  const contextMenuItems = computed<MenuItem[]>(() =>
    contextMenuItem.value
      ? itemMenuItems(contextMenuItem.value, permissions.value)
      : [],
  )

  // A context menu alone is invisible, so each row also has an overflow
  // button opening the same entries.
  const overflowMenu = ref()
  const overflowItem = ref<OrderItemResponse | null>(null)

  function openOverflow(item: OrderItemResponse, event: Event): void {
    overflowItem.value = item
    overflowMenu.value?.toggle(event)
  }

  const overflowMenuItems = computed<MenuItem[]>(() =>
    overflowItem.value
      ? itemMenuItems(overflowItem.value, permissions.value)
      : [],
  )

  // A menu entry has nowhere to show a spinner, so the overflow button does.
  function isBusy(item: OrderItemResponse): boolean {
    return (
      markingOrdered.isPending(item.id) ||
      markingRequested.isPending(item.id) ||
      markingReadyForPickup.isPending(item.id) ||
      settlingLine.isPending(item.id)
    )
  }

  return {
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
  }
}
