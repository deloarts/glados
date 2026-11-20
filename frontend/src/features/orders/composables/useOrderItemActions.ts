import { useI18n } from 'vue-i18n'
import type { MenuItem } from 'openvue/menuitem'

import { Permission } from '@/core/auth/permissions'
import { useClipboard } from '@/core/composables/useClipboard'
import { anyHasAction, hasAction, offersAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'
import type { OrderItemResponse, OrderResponse, OrderStatus } from '../types/ordersResponse'

export interface OrderItemActionHandlers {
  edit(item: OrderItemResponse): void
  move(item: OrderItemResponse): void
  markRequested(item: OrderItemResponse): void
  markOrdered(item: OrderItemResponse): void
  markReadyForPickup(item: OrderItemResponse): void
  deliver(item: OrderItemResponse): void
  viewHistory(item: OrderItemResponse): void
  cancelLine(item: OrderItemResponse): void
  closeShort(item: OrderItemResponse): void
  reopen(item: OrderItemResponse): void
  remove(item: OrderItemResponse): void
}

export interface OrderItemPermissions {
  canWrite: boolean
  canManage: boolean
  /**
   * receive:deliveries, which the backend requires for recording a delivery,
   * since receiving goods is a warehouse action.
   */
  canReceiveDeliveries: boolean
}

/**
 * Whether a line can take a delivery now, as the backend offers it in the
 * line's actions: it is ordered or partially delivered, its order is not
 * canceled and a MADE line's lot is not canceled.
 */
export function isDeliverableLine(item: Pick<OrderItemResponse, 'actions'>): boolean {
  return hasAction(item, 'deliver')
}

/**
 * Whether the order's header can be edited, whether its supplier order
 * numbers can, and whether it takes a new line, as the backend offers them in
 * the order's actions; none is offered on an order someone canceled, and the
 * supplier order numbers not on a delivered one either. `canWrite` is the
 * base permission write:orders.
 */
export const orderActionGates = {
  edit: (order: Pick<OrderResponse, 'actions'>, canWrite: boolean): boolean =>
    canWrite && hasAction(order, 'edit'),
  editSupplierOrderNumbers: (order: Pick<OrderResponse, 'actions'>, canWrite: boolean): boolean =>
    canWrite && hasAction(order, 'edit_supplier_order_numbers'),
  addItem: (order: Pick<OrderResponse, 'actions'>, canWrite: boolean): boolean =>
    canWrite && hasAction(order, 'add_item'),
}

/**
 * The order statuses a line may move to, by the backend's line change rule,
 * which checks the target order like the source. A manager of orders may
 * move to any open order, so the answer is undefined then. Anyone else may
 * move to a draft or requested order, and a pending or requested line also
 * to a partly ordered one, whose lines the supplier does not hold yet stay
 * open to the base permission.
 */
export function moveTargetStatuses(
  line: Pick<OrderItemResponse, 'status'>,
  canManage: boolean,
): readonly OrderStatus[] | undefined {
  if (canManage) return undefined
  return line.status === 'pending' || line.status === 'requested'
    ? ['draft', 'requested', 'partially_ordered']
    : ['draft', 'requested']
}

/** Whether "deliver all" has any line to deliver on this order. */
export function hasDeliverableLines(order: Pick<OrderResponse, 'items'>): boolean {
  return anyHasAction(order.items ?? [], 'deliver')
}

function nothingReceived(item: OrderItemResponse): boolean {
  return (
    item.quantity_delivered + (item.quantity_rejected ?? 0) + (item.quantity_rejected_lost ?? 0) <=
    0
  )
}

/**
 * Whether each action applies to a line: the lifecycle actions come from
 * the line's actions, the permissions from the caller.
 */
export const orderItemActionGates = {
  edit: (item: OrderItemResponse, p: OrderItemPermissions): boolean =>
    p.canWrite && hasAction(item, 'edit'),
  /**
   * A move is a line change like any other: the base permission while the
   * line offers it, and the backend reports manage:orders as blocking once
   * the order or the line is past REQUESTED.
   */
  move: (item: OrderItemResponse, p: OrderItemPermissions): boolean =>
    p.canWrite && hasAction(item, 'move'),
  markRequested: (item: OrderItemResponse, p: OrderItemPermissions): boolean =>
    p.canWrite && hasAction(item, 'mark_requested'),
  markOrdered: (item: OrderItemResponse, p: OrderItemPermissions): boolean =>
    p.canWrite && hasAction(item, 'mark_ordered'),
  markReadyForPickup: (item: OrderItemResponse, p: OrderItemPermissions): boolean =>
    p.canWrite &&
    hasAction(item, 'mark_ready_for_pickup') &&
    item.expected_pickup_date !== null &&
    item.ready_for_pickup_date === null,
  deliver: (item: OrderItemResponse, p: OrderItemPermissions): boolean =>
    p.canReceiveDeliveries && isDeliverableLine(item),
  viewHistory: (item: OrderItemResponse): boolean => (item.delivery_records?.length ?? 0) > 0,
  cancelLine: (item: OrderItemResponse, p: OrderItemPermissions): boolean =>
    p.canWrite && hasAction(item, 'cancel'),
  closeShort: (item: OrderItemResponse, p: OrderItemPermissions): boolean =>
    p.canWrite && hasAction(item, 'close_short'),
  reopen: (item: OrderItemResponse, p: OrderItemPermissions): boolean =>
    p.canWrite && hasAction(item, 'reopen'),
  remove: (item: OrderItemResponse, p: OrderItemPermissions): boolean =>
    p.canWrite && hasAction(item, 'remove'),
  /** The quantity of a line can change only while it is open. */
  editQuantity: (item: OrderItemResponse): boolean => hasAction(item, 'edit_quantity'),
  /**
   * The unit of a line can change only until it received goods, accepted,
   * rejected or lost, as the backend refuses it afterwards.
   */
  editUnit: (item: OrderItemResponse): boolean => nothingReceived(item),
  /** The item and project of a line stay what the received goods came as. */
  editIdentity: (item: OrderItemResponse): boolean => nothingReceived(item),
  /**
   * A delivery row can be corrected while the line takes corrections, if it
   * booked accepted pieces and is no correction itself.
   */
  correctDelivery: (
    item: OrderItemResponse,
    record: { quantity: number; corrects_delivery_id?: number | null },
    p: OrderItemPermissions,
  ): boolean =>
    p.canReceiveDeliveries &&
    hasAction(item, 'correct_delivery') &&
    record.quantity > 0 &&
    !record.corrects_delivery_id,
}

/**
 * The full set of per-line actions as one menu. Entries are disabled rather
 * than omitted, so the menu keeps its shape across statuses. An entry the
 * line's state allows but the user may not take carries the missing
 * permission as its title, which a menu bound to disabledItemTooltipPt
 * shows.
 */
export function useOrderItemActions(handlers: OrderItemActionHandlers) {
  const { t } = useI18n()
  const { copyToClipboard } = useClipboard()
  const { missingForAction } = useMissingPermission()

  function blockedTitle(
    item: OrderItemResponse,
    action: LifecycleAction,
    basePermission: string,
  ): string | undefined {
    if (!offersAction(item, action)) return undefined
    return missingForAction(item, action, basePermission) || undefined
  }

  function itemMenuItems(item: OrderItemResponse, permissions: OrderItemPermissions): MenuItem[] {
    const gates = orderItemActionGates
    return [
      {
        label: t('orders.actions.editItem'),
        icon: 'mdi mdi-pencil',
        disabled: !gates.edit(item, permissions),
        title: blockedTitle(item, 'edit', Permission.WRITE_ORDERS),
        command: () => handlers.edit(item),
      },
      {
        label: t('orders.actions.moveItem'),
        icon: 'mdi mdi-folder-move-outline',
        disabled: !gates.move(item, permissions),
        title: blockedTitle(item, 'move', Permission.WRITE_ORDERS),
        command: () => handlers.move(item),
      },
      { separator: true },
      {
        label: t('orders.actions.markRequested'),
        icon: 'mdi mdi-message-question-outline',
        disabled: !gates.markRequested(item, permissions),
        title: blockedTitle(item, 'mark_requested', Permission.WRITE_ORDERS),
        command: () => handlers.markRequested(item),
      },
      {
        label: t('orders.actions.markOrdered'),
        icon: 'mdi mdi-cart-check',
        disabled: !gates.markOrdered(item, permissions),
        title: blockedTitle(item, 'mark_ordered', Permission.WRITE_ORDERS),
        command: () => handlers.markOrdered(item),
      },
      {
        label: t('orders.actions.markReadyForPickup'),
        icon: 'mdi mdi-hand-back-right-outline',
        disabled: !gates.markReadyForPickup(item, permissions),
        title: blockedTitle(item, 'mark_ready_for_pickup', Permission.WRITE_ORDERS),
        command: () => handlers.markReadyForPickup(item),
      },
      { separator: true },
      {
        label: t('orders.actions.deliver'),
        icon: 'mdi mdi-package-variant-closed-check',
        disabled: !gates.deliver(item, permissions),
        title: blockedTitle(item, 'deliver', Permission.RECEIVE_DELIVERIES),
        command: () => handlers.deliver(item),
      },
      {
        label: t('orders.items.deliveryHistory.title'),
        icon: 'mdi mdi-history',
        disabled: !gates.viewHistory(item),
        command: () => handlers.viewHistory(item),
      },
      { separator: true },
      {
        label: t('orders.actions.cancelItem'),
        icon: 'mdi mdi-close-circle-outline',
        disabled: !gates.cancelLine(item, permissions),
        title: blockedTitle(item, 'cancel', Permission.WRITE_ORDERS),
        command: () => handlers.cancelLine(item),
      },
      {
        label: t('orders.actions.closeShort'),
        icon: 'mdi mdi-content-cut',
        disabled: !gates.closeShort(item, permissions),
        title: blockedTitle(item, 'close_short', Permission.WRITE_ORDERS),
        command: () => handlers.closeShort(item),
      },
      {
        label: t('orders.actions.reopenItem'),
        icon: 'mdi mdi-backup-restore',
        disabled: !gates.reopen(item, permissions),
        title: blockedTitle(item, 'reopen', Permission.WRITE_ORDERS),
        command: () => handlers.reopen(item),
      },
      {
        label: t('orders.actions.removeItem'),
        icon: 'mdi mdi-delete-outline',
        disabled: !gates.remove(item, permissions),
        title: blockedTitle(item, 'remove', Permission.WRITE_ORDERS),
        command: () => handlers.remove(item),
      },
      { separator: true },
      {
        label: t('common.copyUuid'),
        icon: 'mdi mdi-content-copy',
        command: () => void copyToClipboard(item.public_id),
      },
    ]
  }

  return { itemMenuItems }
}
