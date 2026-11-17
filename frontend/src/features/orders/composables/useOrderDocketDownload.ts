import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { extractApiError } from '@/core/utils/errors'
import { usePrint } from '@/shared/print'
import type { OrderResponse } from '../types/ordersResponse'

/**
 * Downloads or prints an order's docket. A multi-page A4 docket is read on
 * screen or filed more often than printed, and downloading needs no
 * printer; printing sends it to the printer set for the Order Docket.
 */
export function useOrderDocketDownload() {
  const { t } = useI18n()
  const toast = useAppToast()
  const printService = usePrint()
  const downloadingDocketId = ref<number | null>(null)

  async function downloadOrderDocket(order: OrderResponse): Promise<void> {
    downloadingDocketId.value = order.id
    try {
      const { warnings } = await printService.download('order_docket', 'order', order.id)
      for (const warning of warnings) {
        toast.warn(order.order_number, warning)
      }
    } catch (e) {
      toast.error(order.order_number, extractApiError(e) ?? t('orders.actions.downloadDocketFailed'))
    } finally {
      downloadingDocketId.value = null
    }
  }

  const printingDocketId = ref<number | null>(null)

  async function printOrderDocket(order: OrderResponse): Promise<void> {
    printingDocketId.value = order.id
    try {
      const [job] = await printService.print({
        root_type: 'order',
        root_id: order.id,
        items: [{ classifier: 'order_docket' }],
      })
      if (job?.status === 'sent') {
        toast.success(order.order_number, t('orders.actions.printDocketSent'))
      } else {
        toast.error(order.order_number, job?.error_message ?? t('orders.actions.printDocketFailed'))
      }
    } catch (e) {
      toast.error(order.order_number, extractApiError(e) ?? t('orders.actions.printDocketFailed'))
    } finally {
      printingDocketId.value = null
    }
  }

  return { downloadingDocketId, downloadOrderDocket, printingDocketId, printOrderDocket }
}
