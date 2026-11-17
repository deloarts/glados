import type { Schemas } from '@/core/api/generated'

export type GlobalSearchHitDetails = Schemas['SearchHitDetails']

export type GlobalSearchHit = Schemas['SearchHitResult']

export type GlobalSearchGroup = Schemas['SearchGroupResult']

export type GlobalSearchResponse = Schemas['GlobalSearchResult']

export type SearchResource = GlobalSearchHit['resource']

export type SearchMatchKind = GlobalSearchHit['match_kind']

export type SearchViaKind = NonNullable<GlobalSearchHit['via_kind']>
