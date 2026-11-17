import { webApi } from '@/core/api/webRequest'

import type { PrinterResponse } from '../types/printerResponse'

export async function archivePrinter(printerId: number): Promise<PrinterResponse> {
  return webApi.post('/printers/{printer_id}/archive', {
    path: { printer_id: printerId },
  })
}
