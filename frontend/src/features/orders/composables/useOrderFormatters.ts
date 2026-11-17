import { useI18n } from 'vue-i18n'
import { isoWeekAndYear, toLocalDayStart, todayStart } from '@/core/utils/dates'
import { formatPrice } from '@/core/utils/currency'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import type { OrderItemResponse, OrderResponse, OrderStatus } from '../types/ordersResponse'

export function useOrderFormatters() {
  const { t } = useI18n()

  function formatPositionPrice(item: OrderItemResponse): string {
    if (item.price === null) return getEmptyPlaceholder()
    return formatPrice(item.price * item.quantity)
  }

  // The backend's net total: the priced lines that are not canceled plus
  // the extra costs, with a discount subtracted.
  function orderTotalPrice(order: OrderResponse): string {
    return formatPrice(order.net_total)
  }

  function orderStatusSeverity(status: OrderStatus): string {
    switch (status) {
      case 'draft':
        return 'secondary'
      case 'requested':
        return 'help'
      case 'partially_ordered':
        return 'info'
      case 'ordered':
        return 'info'
      case 'partially_delivered':
        return 'warn'
      case 'delivered':
        return 'success'
      case 'canceled':
        return 'danger'
      default:
        return 'secondary'
    }
  }

  function orderItemStatusSeverity(status: string): string {
    switch (status) {
      case 'pending':
        return 'secondary'
      case 'requested':
        return 'help'
      case 'ordered':
        return 'info'
      case 'partially_delivered':
        return 'warn'
      case 'delivered':
        return 'success'
      case 'canceled':
        return 'danger'
      default:
        return 'secondary'
    }
  }

  const currentWeek = isoWeekAndYear(todayStart())

  function weekTagFor(dateStr: string | null): { label: string; severity: string } | null {
    if (!dateStr) return null
    // Called with both shapes: ordered_date/delivery_date are instants
    // (resolved to a day in the tenant's timezone), expected_delivery_date is
    // already a calendar date. Appending 'T00:00:00' to the former would
    // produce an Invalid Date and render the tag as "KW NaN".
    const { year, week } = isoWeekAndYear(toLocalDayStart(dateStr))
    let severity: string
    if (year === currentWeek.year && week === currentWeek.week) {
      severity = 'success'
    } else if (year < currentWeek.year || (year === currentWeek.year && week < currentWeek.week)) {
      severity = 'info'
    } else {
      severity = 'warn'
    }
    return { label: `${t('orders.weekPrefix')}${week}`, severity }
  }

  return {
    formatPrice,
    formatPositionPrice,
    orderTotalPrice,
    orderStatusSeverity,
    orderItemStatusSeverity,
    weekTagFor,
  }
}
