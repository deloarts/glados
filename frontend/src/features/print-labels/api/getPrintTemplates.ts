import { webApi } from '@/core/api/webRequest'

import type { PrintTemplateResponse } from '../types/printTemplateResponse'

export async function getPrintTemplates(): Promise<PrintTemplateResponse[]> {
  return webApi.get('/print-templates/')
}
