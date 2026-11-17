import { webApi } from '@/core/api/webRequest'

import type { PrintRequestBody } from '../types/printTemplateRequest'
import type { PrintJobResponse } from '@/features/printers'

/**
 * Manual print of one or more classifiers. A printing failure comes back as
 * a failed job rather than an exception, so check each job's status.
 */
export async function printDocuments(body: PrintRequestBody): Promise<PrintJobResponse[]> {
  return webApi.post('/print/', { body })
}
