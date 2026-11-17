import { webApi } from '@/core/api/webRequest'

import type { PrinterCreateRequest } from '../types/printerRequest'
import type { PrinterResponse } from '../types/printerResponse'

export async function createPrinter(payload: PrinterCreateRequest): Promise<PrinterResponse> {
  return webApi.post('/printers/', { body: payload })
}
