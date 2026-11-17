import { webApi } from '@/core/api/webRequest'

import type { PrintTemplateResponse } from '../types/printTemplateResponse'

export async function resetPrintTemplate(classifier: string): Promise<PrintTemplateResponse> {
  return webApi.post('/print-templates/{classifier}/reset', {
    path: { classifier },
  })
}
