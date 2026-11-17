import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type QuoteRequestCreateRequest = Schemas['QuoteRequestCreateRequest']
export type QuoteRequestUpdateRequest = Schemas['QuoteRequestUpdateRequest']
export type QuoteRequestLineRequest = Schemas['QuoteRequestLineRequest']
export type QuoteRequestLineUpdateRequest = Schemas['QuoteRequestLineUpdateRequest']
export type OfferSaveRequest = Schemas['OfferSaveRequest']
export type QuoteRequestAwardRequest = Schemas['QuoteRequestAwardRequest']
export type QuoteExtraCostRequest = Schemas['QuoteExtraCostRequest']

export type QuoteRequestFilterParams = QueryOf<'/quote-requests/'>
