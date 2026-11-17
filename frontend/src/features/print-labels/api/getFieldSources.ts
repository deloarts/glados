import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'
import type { FieldSourceResponse } from '../types/printTemplateResponse'

export async function getFieldSources(
  classifier: Schemas['PrintClassifier'],
  trigger?: Schemas['PrintTrigger'] | null,
): Promise<FieldSourceResponse[]> {
  return webApi.get('/print-templates/{classifier}/field-sources', {
    path: { classifier },
    query: trigger ? { trigger } : undefined,
  })
}
