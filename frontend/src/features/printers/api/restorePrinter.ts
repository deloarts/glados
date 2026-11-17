import { webApi } from '@/core/api/webRequest'

import type { PrinterResponse } from '../types/printerResponse'

export async function restorePrinter(printerId: number): Promise<PrinterResponse> {
  return webApi.post('/printers/{printer_id}/restore', {
    path: { printer_id: printerId },
  })
}
