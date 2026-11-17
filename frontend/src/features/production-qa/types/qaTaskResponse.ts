import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

/** Embedded on the row, since production orders have no bulk file endpoint. */
export type QaEvidenceFile = Schemas['QaEvidenceFileResponse']

/**
 * One inspection-role production order from the QA worklist. id is the
 * production order id, so every order action applies unchanged.
 */
export type QaTaskResponse = Schemas['QaTaskResponse']

export type QaTaskFilterParams = QueryOf<'/production-qa'>
