import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type SequenceResponse = Schemas['SequenceResponse']
export type SequenceSummaryResponse = Schemas['SequenceSummaryResponse']
export type SequenceCreateRequest = Schemas['SequenceCreateRequest']
export type SequenceUpdateRequest = Schemas['SequenceUpdateRequest']
export type SequenceFrozen = Schemas['SequenceFrozenSchema']

export type SequenceStep = Schemas['SequenceStepSchema']
export type SequenceAction = Schemas['SequenceActionSchema']
export type SequenceTransition = Schemas['SequenceTransitionSchema']
export type SequenceConditionTerm = Schemas['SequenceConditionTermSchema']
export type SequenceVariantValue = Schemas['SequenceVariantValueSchema']
export type SequenceActionQualifier = NonNullable<SequenceAction['qualifier']>
export type SequenceConditionKind = SequenceConditionTerm['kind']

export type ProductVariant = Schemas['ProductVariantResponse']
export type ProductVariantRequest = Schemas['ProductVariantRequest']

/** A transition target that is not a step key. */
export const TARGET_NEXT = 'next'
export const TARGET_END = 'end'

/** Fields the sequence list can be sorted by on the server; title sorts by the name. */
export type SequenceSortBy = NonNullable<SequenceListParams['order_by']>

export type SequenceListParams = QueryOf<'/sequences'>

/** Where a sequence stands: a draft, released, or superseded by a newer revision. */
export type SequenceStatus = 'draft' | 'released' | 'superseded'
