import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { anyHasAction, offersAction } from '@/core/utils/lifecycleActions'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useOrdersStore } from '../stores/ordersStore'
import { hasDeliverableLines } from './useOrderItemActions'

import type { MenuItem } from 'openvue/menuitem'
import type { OrderResponse } from '../types/ordersResponse'

/** What the order page hands in: its order, its permissions and its reload. */
export interface OrderDetailToolbarDeps {
  order: Ref<OrderResponse | null>
  canWrite: ComputedRef<boolean>
  canReceiveDeliveries: ComputedRef<boolean>
  canSendMail: ComputedRef<boolean>
  reload: (options: { quiet: boolean }) => Promise<unknown>
  composeOrderMail: (order: OrderResponse, type: 'request' | 'order') => Promise<void>
  openDeliverAll: () => void
}

/**
 * The order-level actions of the order page's controls bar: Add Item with
 * its menu, the mark-all actions and the mails, plus the menus the compact
 * toolbar folds them into. The actions come from the order and its lines and
 * are gated with disabled rather than v-if, so the bar does not reshuffle as
 * the status changes.
 */
export function useOrderDetailToolbar(deps: OrderDetailToolbarDeps) {
  const { t } = useI18n()
  const ordersStore = useOrdersStore()
  const { order, canWrite, canReceiveDeliveries, canSendMail } = deps

  const hasPending = computed(() => anyHasAction(order.value?.items ?? [], 'mark_requested'))
  const hasPendingOrRequested = computed(() =>
    anyHasAction(order.value?.items ?? [], 'mark_ordered'),
  )
  const hasDeliverable = computed(() => (order.value ? hasDeliverableLines(order.value) : false))

  // A mark-all action names the permission it lacks: write:orders, else the
  // extra permission the backend blocks it by on the lines whose state
  // allows it, which is manage:orders on a submitted order.
  const { missing, missingForAction } = useMissingPermission()
  function markAllBlocked(action: LifecycleAction): string {
    const lacking = missing(Permission.WRITE_ORDERS)
    if (lacking) return lacking
    const items = order.value?.items ?? []
    if (anyHasAction(items, action)) return ''
    const blocked = items.find((item) => offersAction(item, action))
    return blocked ? missingForAction(blocked, action) : ''
  }
  const markAllRequestedBlocked = computed(() => markAllBlocked('mark_requested'))
  const markAllOrderedBlocked = computed(() => markAllBlocked('mark_ordered'))
  const deliverAllBlocked = computed(() => missing(Permission.RECEIVE_DELIVERIES))
  const sendMailBlocked = computed(() => missing(Permission.SEND_MAIL))

  const markingRequested = ref(false)
  const markingOrdered = ref(false)

  async function markAllRequested(): Promise<void> {
    if (!order.value) return
    markingRequested.value = true
    try {
      await ordersStore.markAllItemsRequested(order.value.id)
      await deps.reload({ quiet: true })
    } finally {
      markingRequested.value = false
    }
  }

  async function markAllOrdered(): Promise<void> {
    if (!order.value) return
    markingOrdered.value = true
    try {
      await ordersStore.markAllItemsOrdered(order.value.id)
      await deps.reload({ quiet: true })
    } finally {
      markingOrdered.value = false
    }
  }

  const showAddItem = ref(false)
  const addItemVirtual = ref(false)

  function openAddItem(isVirtual: boolean): void {
    addItemVirtual.value = isVirtual
    showAddItem.value = true
  }

  const addItemMenuItems = computed<MenuItem[]>(() => [
    {
      label: t('orders.actions.addItemMenu.bought'),
      icon: 'mdi mdi-cart-outline',
      command: () => openAddItem(false),
    },
    {
      label: t('orders.actions.addItemMenu.virtual'),
      icon: 'mdi mdi-file-outline',
      command: () => openAddItem(true),
    },
    {
      label: t('orders.actions.addItemMenu.made'),
      icon: 'mdi mdi-cog-outline',
      disabled: true,
      title: t('orders.actions.addItemMenu.madeComingSoon'),
    },
  ])

  function onMailAction(current: OrderResponse, type: 'request' | 'order'): void {
    void deps.composeOrderMail(current, type)
  }

  // The compact menus mirror the desktop buttons item for item. The buttons
  // stay hand-written, since they show a per-button loading state.
  const markAllMenuItems = computed<MenuItem[]>(() => [
    {
      label: t('orders.actions.markAllRequested'),
      icon: 'mdi mdi-message-question-outline',
      disabled: !canWrite.value || !hasPending.value,
      title: markAllRequestedBlocked.value || undefined,
      command: () => void markAllRequested(),
    },
    {
      label: t('orders.actions.markAllOrdered'),
      icon: 'mdi mdi-cart-check',
      disabled: !canWrite.value || !hasPendingOrRequested.value,
      title: markAllOrderedBlocked.value || undefined,
      command: () => void markAllOrdered(),
    },
    {
      label: t('orders.actions.deliverAll'),
      icon: 'mdi mdi-package-variant-closed-check',
      disabled: !canReceiveDeliveries.value || !hasDeliverable.value,
      title: deliverAllBlocked.value || undefined,
      command: deps.openDeliverAll,
    },
  ])

  const mailMenuItems = computed<MenuItem[]>(() => [
    {
      label: t('orders.actions.requestMail'),
      icon: 'mdi mdi-email-arrow-right-outline',
      disabled: !canSendMail.value,
      title: sendMailBlocked.value || undefined,
      command: () => {
        if (order.value) onMailAction(order.value, 'request')
      },
    },
    {
      label: t('orders.actions.orderMail'),
      icon: 'mdi mdi-email-fast-outline',
      disabled: !canSendMail.value,
      title: sendMailBlocked.value || undefined,
      command: () => {
        if (order.value) onMailAction(order.value, 'order')
      },
    },
  ])

  return {
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
  }
}

// Unpacks MenuItem for the desktop buttons: label may be a function, and
// command expects Menu's event wrapper.
export function menuItemLabel(item: MenuItem): string {
  return typeof item.label === 'function' ? item.label() : (item.label ?? '')
}

export function runMenuItem(item: MenuItem, event: Event): void {
  item.command?.({ originalEvent: event, item })
}
