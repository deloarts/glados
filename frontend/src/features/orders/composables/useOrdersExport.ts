import { useI18n } from 'vue-i18n'

import { getDisplayCurrency } from '@/core/utils/currency'
import { exportFilename, useSpreadsheetExport } from '@/shared/spreadsheet-export'

import { getOrders } from '../api/getOrders'
import { useOrdersStore } from '../stores/ordersStore'
import { orderLineRows, ordersExportColumns } from '../utils/ordersExport'
import { useOrdersQuery } from './useOrdersQuery'

import type { OrderResponse } from '../types/ordersResponse'
import type { OrderLineRow } from '../utils/ordersExport'

/**
 * The spreadsheet export of the orders table: every order of the current
 * filter and sort, written as one row per order line. The table has no row
 * selection, so there is no selected scope. The row limits count orders.
 */
export function useOrdersExport() {
  const { t } = useI18n()
  const ordersStore = useOrdersStore()
  const { listParams } = useOrdersQuery()

  return useSpreadsheetExport<OrderResponse, OrderLineRow>({
    total: () => ordersStore.total,
    selected: () => [],
    fetchPage: (window, signal) => getOrders({ ...listParams(), ...window }, { signal }),
    toSheetRows: orderLineRows,
    columns: () => ordersExportColumns(t, getDisplayCurrency()),
    format: () => ({
      sheetName: t('orders.export.sheetName'),
      filename: exportFilename(t('orders.export.filename')),
    }),
  })
}
