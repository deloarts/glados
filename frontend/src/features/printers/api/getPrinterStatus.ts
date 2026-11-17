import { webApi } from '@/core/api/webRequest'

import type { PrinterStatusResponse } from '../types/printerResponse'

// Queries the printer for identity + status (~HI/~HS or IPP attributes).
// Prints nothing.
export async function getPrinterStatus(printerId: number): Promise<PrinterStatusResponse> {
  return webApi.get('/printers/{printer_id}/status', {
    path: { printer_id: printerId },
  })
}
