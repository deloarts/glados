import { webApi } from '@/core/api/webRequest'

import type { PrinterUpdateRequest } from '../types/printerRequest'
import type { PrinterResponse } from '../types/printerResponse'

export async function updatePrinter(
  printerId: number,
  payload: PrinterUpdateRequest,
): Promise<PrinterResponse> {
  return webApi.patch('/printers/{printer_id}', {
    path: { printer_id: printerId },
    body: payload,
  })
}
