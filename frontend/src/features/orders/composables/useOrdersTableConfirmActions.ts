import { type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useConfirm } from 'openvue/useconfirm'

import { extractApiError } from '@/core/utils/errors'
import { useOrdersStore } from '../stores/ordersStore'

import type { OrderItemResponse, OrderResponse } from '../types/ordersResponse'
import type { OrderMailType } from './useOrderMailComposer'

// The confirm flows of the orders table: removing an item, canceling an
// order and offering to notify the supplier. The store mutations refresh
// the rows this table renders, so no reload is needed.
export function useOrdersTableConfirmActions(
  canSendMail: Ref<boolean>,
  composeOrderMail: (order: OrderResponse, mailType: OrderMailType) => Promise<void>,
) {
  const { t } = useI18n()
  const toast = useAppToast()
  const confirm = useConfirm()
  const ordersStore = useOrdersStore()

  function openRemoveItemDialog(orderId: number, item: OrderItemResponse): void {
    async function onAccept(): Promise<void> {
      try {
        await ordersStore.removeItem(orderId, item.id, item.edit_version)
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

  function startCancelConfirm(order: OrderResponse): void {
    async function onAccept(): Promise<void> {
      try {
        await ordersStore.cancel(order.id, order.edit_version)
        if (canSendMail.value) confirmNotifySupplierOfCancellation(order)
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

  return { openRemoveItemDialog, startCancelConfirm }
}
