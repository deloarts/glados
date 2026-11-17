import { webApi } from '@/core/api/webRequest'

import type { PrintTemplateUpdateRequest } from '../types/printTemplateRequest'
import type { PrintTemplateResponse } from '../types/printTemplateResponse'

export async function updatePrintTemplate(
  classifier: string,
  payload: PrintTemplateUpdateRequest,
): Promise<PrintTemplateResponse> {
  return webApi.patch('/print-templates/{classifier}', {
    path: { classifier },
    body: payload,
  })
}
