import { webApi } from '@/core/api/webRequest'

// Sends a built-in self-test job, no template required. Backend returns 204.
export async function testPrintPrinter(printerId: number): Promise<void> {
  await webApi.post('/printers/{printer_id}/test-print', { path: { printer_id: printerId } })
}
