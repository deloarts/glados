import type { Schemas } from '@/core/api/generated'
import type { MadeItemDemandResponse } from '@/features/made-items'
import type { LotSummaryResponse } from '@/features/production'

// The made demands and lots are refined to the role unions of their own list
// types, as getMadeItemDemands and getLots refine them.
export type MeetingTodoSourceResponse = Schemas['MeetingTodoSourceResponse']

export type TodoSourcesResponse = Omit<Schemas['TodoSourcesResponse'], 'made_demands' | 'lots'> & {
  made_demands: MadeItemDemandResponse[]
  lots: LotSummaryResponse[]
}
