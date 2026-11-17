import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { PrinterFilterParams } from '../types/printerRequest'
import type { PrinterResponse } from '../types/printerResponse'

export async function getPrinters(
  params?: PrinterFilterParams,
): Promise<PageResponse<PrinterResponse>> {
  return webApi.get('/printers/', { query: params })
}
