import { webApi } from '@/core/api/webRequest'

import type { PrintJobResponse } from '@/features/printers'

/**
 * Scrap tag print scoped to a lot; the backend resolves the lot's latest
 * scrap or lost-at-receipt record. Never rejects on a printing failure.
 */
export async function printLotScrapTag(
  lotId: number,
  options: { printerId?: number; copies?: number } = {},
): Promise<PrintJobResponse> {
  return webApi.post('/production-lots/{lot_id}/print', {
    path: { lot_id: lotId },
    body: {
      printer_id: options.printerId ?? null,
      copies: options.copies ?? null,
    },
  })
}
