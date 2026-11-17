import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type CalculationResponse = Schemas['CalculationResponse']
export type CalculationSummaryResponse = Schemas['CalculationSummaryResponse']
export type CalculationCreateRequest = Schemas['CalculationCreateRequest']
export type CalculationUpdateRequest = Schemas['CalculationUpdateRequest']

/** Who a calculation belongs to. Neither project nor product means personal. */
export type CalculationOwner =
  | { kind: 'personal' }
  | { kind: 'project'; id: number; label: string }
  | { kind: 'product'; id: number; label: string }

export type CalculationListParams = QueryOf<'/calculations'>

/** Fields the calculation list can be sorted by on the server. */
export type CalculationSortBy = NonNullable<CalculationListParams['order_by']>
