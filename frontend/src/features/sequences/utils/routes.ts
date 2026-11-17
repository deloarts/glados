import type { RouteLocationRaw } from 'vue-router'

import type { DocumentPageAction } from '@/shared/documents'

/** The page of one sequence revision, optionally on one of its views or with a step for the page to take. */
export function sequenceLocation(
  sequence: { id: number; product_id: number },
  options: { view?: string; action?: DocumentPageAction } = {},
): RouteLocationRaw {
  return {
    name: 'SequenceDetail',
    params: { id: sequence.product_id, sequenceId: sequence.id, ...(options.view ? { view: options.view } : {}) },
    query: options.action ? { action: options.action } : {},
  }
}
