import { webApi } from '@/core/api/webRequest'

import type { PageResponse } from '@/core/api/types'
import type { PrintJobFilterParams } from '../types/printJobRequest'
import type { PrintJobResponse } from '../types/printJobResponse'

export async function getPrintJobs(
  params?: PrintJobFilterParams,
): Promise<PageResponse<PrintJobResponse>> {
  return webApi.get('/print-jobs/', { query: params })
}
