import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type ContactFilterParams = QueryOf<'/contacts'>
export type ContactSortBy = NonNullable<ContactFilterParams['order_by']>

export type ContactCreateRequest = Schemas['ContactCreateRequest']

export type ContactUpdateRequest = Schemas['ContactUpdateRequest']
